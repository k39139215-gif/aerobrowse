//! Native CDP pipe transport with correlation, bounded frames and an isolated process.
use crate::native_network::NetworkPolicy;
use crate::pruner::SemanticPruner;
use crate::security::MAX_BYTES;
use base64::{engine::general_purpose::STANDARD, Engine};
use serde_json::{json, Value};
use std::collections::HashSet;
#[cfg(target_os = "linux")]
use std::process::Stdio;
use std::time::Duration;
use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};
#[cfg(target_os = "linux")]
use tokio::process::Command;
use tokio::process::{Child, ChildStdin, ChildStdout};

const FRAME_LIMIT: usize = 12 * 1024 * 1024;
const OPERATION_TIMEOUT: Duration = Duration::from_secs(30);
const ACTION_RUNTIME: &str = include_str!("../../aerobrowse/action_runtime.js");

pub struct FidelitySession {
    child: Child,
    input: ChildStdin,
    output: BufReader<ChildStdout>,
    #[cfg(target_os = "linux")]
    resources: LinuxResources,
    policy: NetworkPolicy,
    next_id: u64,
    pending_background: HashSet<u64>,
    session: String,
    context: Option<u64>,
    generation: String,
    serial: u64,
    nonce: String,
    network_error: Option<String>,
    redirect_count: usize,
    loaded: bool,
    poisoned: bool,
}

#[cfg(target_os = "linux")]
struct LinuxResources {
    path: std::path::PathBuf,
    guardian: Option<std::process::Child>,
    lease: Option<std::process::ChildStdin>,
}
#[cfg(target_os = "linux")]
impl LinuxResources {
    fn create() -> Result<Self, String> {
        use std::fs;
        use std::time::{SystemTime, UNIX_EPOCH};
        let root =
            std::env::var_os("AEROBROWSE_CGROUP_ROOT").ok_or("RESOURCE_ISOLATION_UNAVAILABLE")?;
        let root = std::path::PathBuf::from(root)
            .canonicalize()
            .map_err(|_| "RESOURCE_ISOLATION_UNAVAILABLE")?;
        if !root.starts_with("/sys/fs/cgroup") {
            return Err("RESOURCE_ISOLATION_UNAVAILABLE".into());
        }
        let serial = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| "RUNTIME_CLOCK_ERROR")?
            .as_nanos();
        let path = root.join(format!("aero-native-{}-{serial}", std::process::id()));
        fs::create_dir(&path).map_err(|_| "RESOURCE_ISOLATION_UNAVAILABLE")?;
        let mut resources = Self {
            path,
            guardian: None,
            lease: None,
        };
        for (key, value) in [
            ("memory.max", "1073741824"),
            ("memory.swap.max", "0"),
            ("pids.max", "256"),
            ("cpu.max", "100000 100000"),
        ] {
            fs::write(resources.path.join(key), value)
                .map_err(|_| "RESOURCE_ISOLATION_UNAVAILABLE")?;
        }
        let mut guardian = std::process::Command::new(
            std::env::current_exe().map_err(|_| "GUARDIAN_UNAVAILABLE")?,
        )
        .arg("native-guardian")
        .arg(&resources.path)
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "GUARDIAN_UNAVAILABLE")?;
        resources.lease = guardian.stdin.take();
        resources.guardian = Some(guardian);
        Ok(resources)
    }
    fn attach(&self, pid: u32) -> Result<(), String> {
        std::fs::write(self.path.join("cgroup.procs"), pid.to_string())
            .map_err(|_| "RESOURCE_ISOLATION_UNAVAILABLE".into())
    }
    fn healthy(&self) -> Result<(), String> {
        for name in ["pids.events", "memory.events"] {
            let text = std::fs::read_to_string(self.path.join(name))
                .map_err(|_| "RESOURCE_ISOLATION_UNAVAILABLE")?;
            for line in text.lines() {
                if let Some((key, value)) = line.split_once(' ') {
                    if ["max", "oom", "oom_kill"].contains(&key) && value != "0" {
                        return Err("WORKER_RESOURCE_LIMIT".into());
                    }
                }
            }
        }
        Ok(())
    }
}
#[cfg(target_os = "linux")]
impl Drop for LinuxResources {
    fn drop(&mut self) {
        self.lease.take();
        if let Some(mut guardian) = self.guardian.take() {
            if guardian.wait().is_err() {
                eprintln!("native_cleanup outcome=error code=GUARDIAN_WAIT_FAILED");
            }
        } else if std::fs::remove_dir(&self.path).is_err() {
            eprintln!("native_cleanup outcome=error code=CGROUP_CLEANUP_FAILED");
        }
    }
}

pub fn guardian(path: std::path::PathBuf) -> Result<(), String> {
    #[cfg(not(target_os = "linux"))]
    {
        let _ = path;
        Err("NETWORK_ISOLATION_UNAVAILABLE".into())
    }
    #[cfg(target_os = "linux")]
    {
        use std::io::Read;
        let root =
            std::env::var_os("AEROBROWSE_CGROUP_ROOT").ok_or("RESOURCE_ISOLATION_UNAVAILABLE")?;
        let root = std::path::PathBuf::from(root)
            .canonicalize()
            .map_err(|_| "RESOURCE_ISOLATION_UNAVAILABLE")?;
        let checked = path
            .canonicalize()
            .map_err(|_| "RESOURCE_ISOLATION_UNAVAILABLE")?;
        if checked.parent() != Some(root.as_path())
            || !checked
                .file_name()
                .and_then(|s| s.to_str())
                .is_some_and(|s| s.starts_with("aero-native-"))
            || !root.starts_with("/sys/fs/cgroup")
        {
            return Err("INVALID_RUNTIME_CONFIG".into());
        }
        let mut byte = [0];
        loop {
            match std::io::stdin().read(&mut byte) {
                Ok(0) => break,
                Ok(_) => {}
                Err(error) if error.kind() == std::io::ErrorKind::Interrupted => continue,
                Err(_) => break,
            }
        }
        std::fs::write(checked.join("cgroup.kill"), "1").map_err(|_| "CGROUP_KILL_FAILED")?;
        for _ in 0..500 {
            match std::fs::remove_dir(&checked) {
                Ok(()) => return Ok(()),
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(()),
                Err(_) => std::thread::sleep(Duration::from_millis(10)),
            }
        }
        Err("CGROUP_CLEANUP_FAILED".into())
    }
}

impl FidelitySession {
    #[cfg(not(target_os = "linux"))]
    pub async fn launch() -> Result<Self, String> {
        Err("NETWORK_ISOLATION_UNAVAILABLE".into())
    }

    #[cfg(target_os = "linux")]
    pub async fn launch() -> Result<Self, String> {
        let browser =
            std::env::var_os("AEROBROWSE_CHROMIUM").ok_or("NETWORK_ISOLATION_UNAVAILABLE")?;
        let browser = tokio::fs::canonicalize(std::path::PathBuf::from(browser))
            .await
            .map_err(|_| "NETWORK_ISOLATION_UNAVAILABLE")?;
        if !tokio::fs::metadata(&browser)
            .await
            .map_err(|_| "NETWORK_ISOLATION_UNAVAILABLE")?
            .is_file()
        {
            return Err("NETWORK_ISOLATION_UNAVAILABLE".into());
        }
        let resources = tokio::task::spawn_blocking(LinuxResources::create)
            .await
            .map_err(|_| "RESOURCE_ISOLATION_UNAVAILABLE")??;
        // The shell consumes one gate line before allocating descendants. CDP is
        // inherited as fd3/4; no unauthenticated TCP debugging endpoint exists.
        let mut command = Command::new("/bin/sh");
        command.args([
            "-c",
            "IFS= read -r gate || exit 1; exec 3<&0 4>&1; exec \"$@\"",
            "aero-native",
            "bwrap",
        ]);
        command.args([
            "--unshare-user",
            "--uid",
            "0",
            "--gid",
            "0",
            "--unshare-net",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--die-with-parent",
            "--new-session",
            "--cap-drop",
            "ALL",
            "--clearenv",
            "--setenv",
            "HOME",
            "/home/browser",
            "--setenv",
            "TMPDIR",
            "/workspace/tmp",
            "--setenv",
            "LANG",
            "C.UTF-8",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/workspace",
            "--dir",
            "/workspace/tmp",
            "--tmpfs",
            "/home",
            "--dir",
            "/home/browser",
            "--tmpfs",
            "/run",
            "--chdir",
            "/workspace",
            "--preserve-fds",
            "2",
        ]);
        for directory in [
            "/lib",
            "/lib64",
            "/usr/lib",
            "/usr/lib64",
            "/usr/share/fonts",
            "/usr/share/fontconfig",
            "/usr/share/glib-2.0",
            "/etc/fonts",
            "/etc/ssl/certs",
            "/etc/ld.so.cache",
        ] {
            if std::path::Path::new(directory).exists() {
                command.args(["--ro-bind", directory, directory]);
            }
        }
        let distribution = browser.parent().ok_or("NETWORK_ISOLATION_UNAVAILABLE")?;
        command
            .arg("--ro-bind")
            .arg(distribution)
            .arg(distribution)
            .arg("--")
            .arg(browser);
        command.args([
            "--headless=new",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--remote-debugging-pipe",
            "--user-data-dir=/workspace/profile",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-extensions",
            "--disable-quic",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            "about:blank",
        ]);
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .kill_on_drop(true);
        let mut child = command
            .spawn()
            .map_err(|_| "NETWORK_ISOLATION_UNAVAILABLE")?;
        resources.attach(child.id().ok_or("BROWSER_CRASHED")?)?;
        let mut input = child.stdin.take().ok_or("BROWSER_PIPE_ERROR")?;
        let output = BufReader::new(child.stdout.take().ok_or("BROWSER_PIPE_ERROR")?);
        input
            .write_all(b"ready\n")
            .await
            .map_err(|_| "BROWSER_PIPE_ERROR")?;
        let mut session = Self {
            child,
            input,
            output,
            resources,
            policy: NetworkPolicy::from_environment()?,
            next_id: 0,
            pending_background: HashSet::new(),
            session: String::new(),
            context: None,
            generation: String::new(),
            serial: 0,
            network_error: None,
            redirect_count: 0,
            loaded: false,
            poisoned: false,
            nonce: tokio::fs::read_to_string("/proc/sys/kernel/random/uuid")
                .await
                .map_err(|_| "ENTROPY_UNAVAILABLE")?
                .trim()
                .replace('-', ""),
        };
        let init = tokio::time::timeout(Duration::from_secs(15), session.initialize()).await;
        match init {
            Ok(Ok(())) => Ok(session),
            Ok(Err(code)) => Err(code),
            Err(_) => Err("BROWSER_START_TIMEOUT".into()),
        }
    }
    #[cfg(target_os = "linux")]
    async fn initialize(&mut self) -> Result<(), String> {
        self.call("Target.setDiscoverTargets", json!({"discover":true}), false)
            .await?;
        let context = self
            .call(
                "Target.createBrowserContext",
                json!({"disposeOnDetach":true}),
                false,
            )
            .await?;
        let target = self
            .call(
                "Target.createTarget",
                json!({"url":"about:blank", "browserContextId":context["browserContextId"]}),
                false,
            )
            .await?;
        let attached = self
            .call(
                "Target.attachToTarget",
                json!({"targetId":target["targetId"],"flatten":true}),
                false,
            )
            .await?;
        self.session = attached["sessionId"]
            .as_str()
            .ok_or("CDP_PROTOCOL_ERROR")?
            .into();
        self.call("Page.enable", json!({}), true).await?;
        self.call("Runtime.enable", json!({}), true).await?;
        self.call("Network.enable", json!({}), true).await?;
        self.call(
            "Network.setBypassServiceWorker",
            json!({"bypass":true}),
            true,
        )
        .await?;
        self.call(
            "Browser.setDownloadBehavior",
            json!({"behavior":"deny","browserContextId":context["browserContextId"]}),
            false,
        )
        .await?;
        self.call(
            "Fetch.enable",
            json!({"patterns":[{"urlPattern":"*", "requestStage":"Request"}]}),
            true,
        )
        .await?;
        Ok(())
    }
    async fn send(&mut self, method: &str, params: Value, page: bool) -> Result<u64, String> {
        self.next_id = self.next_id.checked_add(1).ok_or("CDP_ID_EXHAUSTED")?;
        let mut frame = json!({"id":self.next_id,"method":method,"params":params});
        if page {
            frame["sessionId"] = json!(self.session);
        }
        let mut raw = serde_json::to_vec(&frame).map_err(|_| "CDP_SERIALIZATION_ERROR")?;
        if raw.len() > FRAME_LIMIT {
            return Err("REQUEST_TOO_LARGE".into());
        }
        raw.push(0);
        self.input
            .write_all(&raw)
            .await
            .map_err(|_| "BROWSER_DISCONNECTED")?;
        self.input
            .flush()
            .await
            .map_err(|_| "BROWSER_DISCONNECTED")?;
        Ok(self.next_id)
    }
    async fn background(&mut self, method: &str, params: Value, page: bool) -> Result<(), String> {
        if self.pending_background.len() >= 128 {
            return Err("CDP_CAPACITY_EXCEEDED".into());
        }
        let id = self.send(method, params, page).await?;
        self.pending_background.insert(id);
        Ok(())
    }
    async fn read(&mut self) -> Result<Value, String> {
        let mut raw = Vec::new();
        let bytes = (&mut self.output)
            .take(FRAME_LIMIT as u64 + 1)
            .read_until(0, &mut raw)
            .await
            .map_err(|_| "BROWSER_DISCONNECTED")?;
        if bytes == 0 {
            return Err("BROWSER_DISCONNECTED".into());
        }
        if bytes > FRAME_LIMIT || raw.last() != Some(&0) {
            return Err("CDP_FRAME_TOO_LARGE".into());
        }
        raw.pop();
        let frame: Value = serde_json::from_slice(&raw).map_err(|_| "CDP_PROTOCOL_ERROR")?;
        if !frame.is_object() {
            return Err("CDP_PROTOCOL_ERROR".into());
        }
        Ok(frame)
    }
    async fn call(&mut self, method: &str, params: Value, page: bool) -> Result<Value, String> {
        let id = self.send(method, params, page).await?;
        loop {
            let frame = self.read().await?;
            if let Some(response_id) = frame["id"].as_u64() {
                if response_id == id {
                    if frame.get("error").is_some() {
                        return Err("CDP_OPERATION_FAILED".into());
                    }
                    return frame
                        .get("result")
                        .cloned()
                        .ok_or_else(|| "CDP_PROTOCOL_ERROR".into());
                }
                if !self.pending_background.remove(&response_id) {
                    return Err("CDP_CORRELATION_ERROR".into());
                }
                if frame.get("error").is_some() {
                    return Err("CDP_BROKER_FAILED".into());
                }
            } else {
                self.event(frame).await?;
            }
        }
    }
    async fn event(&mut self, event: Value) -> Result<(), String> {
        match event["method"].as_str() {
            Some("Fetch.requestPaused") => {
                let params = &event["params"];
                if params.get("redirectedRequestId").is_some() {
                    self.redirect_count += 1;
                    if self.redirect_count > 5 {
                        self.network_error = Some("TOO_MANY_REDIRECTS".into());
                    }
                }
                let result = if let Some(code) = &self.network_error {
                    Err(code.clone())
                } else {
                    self.policy.fulfill(params).await
                };
                match result {
                    Ok(response) => {
                        self.background("Fetch.fulfillRequest", response, true)
                            .await?
                    }
                    Err(code) => {
                        self.network_error = Some(code);
                        self.background("Fetch.failRequest", json!({"requestId":params["requestId"],"errorReason":"BlockedByClient"}), true).await?;
                    }
                }
            }
            Some("Page.domContentEventFired") => self.loaded = true,
            Some("Inspector.targetCrashed" | "Target.targetCrashed" | "Inspector.detached") => {
                return Err("BROWSER_CRASHED".into())
            }
            Some("Runtime.executionContextsCleared") => {
                self.context = None;
                self.generation.clear();
            }
            Some("Target.targetCreated") => {
                let target = &event["params"]["targetInfo"];
                if target["type"].as_str() == Some("page") && target["openerId"].is_string() {
                    self.background(
                        "Target.closeTarget",
                        json!({"targetId":target["targetId"]}),
                        false,
                    )
                    .await?;
                }
            }
            _ => {}
        }
        Ok(())
    }
    async fn evaluate(&mut self, expression: String) -> Result<Value, String> {
        let context = self.context.ok_or("STALE_ACTION_ID")?;
        let result = self
            .call(
                "Runtime.evaluate",
                json!({"expression":expression,"contextId":context,"returnByValue":true}),
                true,
            )
            .await?;
        if result.get("exceptionDetails").is_some() {
            return Err("ACTION_CONTEXT_FAILED".into());
        }
        result["result"]
            .get("value")
            .cloned()
            .ok_or_else(|| "CDP_PROTOCOL_ERROR".into())
    }
    async fn live_snapshot(&mut self) -> Result<Value, String> {
        if let Some(code) = &self.network_error {
            return Err(code.clone());
        }
        let frame = self.call("Page.getFrameTree", json!({}), true).await?;
        let world = self.call("Page.createIsolatedWorld", json!({"frameId":frame["frameTree"]["frame"]["id"],"worldName":"AeroBrowse actions"}), true).await?;
        self.context = Some(
            world["executionContextId"]
                .as_u64()
                .ok_or("CDP_PROTOCOL_ERROR")?,
        );
        self.evaluate(format!("if(globalThis.__aeroState)globalThis.__aeroState.dispose();globalThis.__aeroState={ACTION_RUNTIME};true")).await?;
        self.serial = self.serial.checked_add(1).ok_or("GENERATION_EXHAUSTED")?;
        self.generation = format!(
            "{:016x}{:016x}",
            u64::from_str_radix(self.nonce.get(..16).ok_or("ENTROPY_UNAVAILABLE")?, 16)
                .map_err(|_| "ENTROPY_UNAVAILABLE")?,
            self.serial
        );
        let live = self
            .evaluate(format!(
                "globalThis.__aeroState.snapshot({},{MAX_BYTES})",
                json!(self.generation)
            ))
            .await?;
        if live.get("error").is_some() {
            return Err("HTML_TOO_LARGE".into());
        }
        let url = live["url"].as_str().ok_or("SNAPSHOT_FAILED")?;
        self.policy.parse(url)?;
        let html = live["html"].as_str().ok_or("SNAPSHOT_FAILED")?;
        let parsed = SemanticPruner::prune(html, url)?;
        let mut result = serde_json::to_value(parsed).map_err(|_| "SERIALIZATION_ERROR")?;
        result["success"] = json!(true);
        result["url"] = json!(url);
        result["engine"] = json!("fidelity");
        result["actions"] = live["actions"].clone();
        result["generation"] = json!(self.generation);
        result["input_mode"] = json!("synthetic_dom");
        Ok(result)
    }
    async fn navigate_inner(&mut self, url: &str) -> Result<Value, String> {
        self.policy.parse(url)?;
        self.network_error = None;
        self.redirect_count = 0;
        self.loaded = false;
        self.context = None;
        self.generation.clear();
        let result = self.call("Page.navigate", json!({"url":url}), true).await?;
        if result.get("errorText").is_some() {
            return Err(self
                .network_error
                .clone()
                .unwrap_or_else(|| "NAVIGATION_FAILED".into()));
        }
        while !self.loaded {
            let event = self.read().await?;
            if let Some(id) = event["id"].as_u64() {
                if !self.pending_background.remove(&id) || event.get("error").is_some() {
                    return Err("CDP_BROKER_FAILED".into());
                }
            } else {
                self.event(event).await?;
            }
        }
        self.live_snapshot().await
    }
    async fn bounded(&mut self, operation: &Value) -> Result<Value, String> {
        if self.poisoned {
            return Err("SESSION_CLOSED".into());
        }
        #[cfg(target_os = "linux")]
        self.resources.healthy()?;
        let result = tokio::time::timeout(OPERATION_TIMEOUT, self.execute(operation)).await;
        match result {
            Ok(Ok(value)) => Ok(value),
            Ok(Err(code)) => {
                if [
                    "BROWSER_CRASHED",
                    "BROWSER_DISCONNECTED",
                    "CDP_CORRELATION_ERROR",
                    "CDP_FRAME_TOO_LARGE",
                    "CDP_PROTOCOL_ERROR",
                ]
                .contains(&code.as_str())
                {
                    self.poisoned = true;
                    self.child
                        .start_kill()
                        .map_err(|_| "BROWSER_TERMINATION_FAILED")?;
                }
                Err(code)
            }
            Err(_) => {
                self.poisoned = true;
                self.child
                    .start_kill()
                    .map_err(|_| "BROWSER_TERMINATION_FAILED")?;
                Err("TIMEOUT".into())
            }
        }
    }
    pub async fn navigate(&mut self, url: &str) -> Result<Value, String> {
        self.bounded(&json!({"operation":"navigate","url":url}))
            .await
    }
    async fn execute(&mut self, request: &Value) -> Result<Value, String> {
        match request["operation"].as_str().ok_or("INVALID_REQUEST")? {
            "navigate" => {
                self.navigate_inner(request["url"].as_str().ok_or("INVALID_URL")?)
                    .await
            }
            "snapshot" => self.live_snapshot().await,
            "click" | "fill" | "select" | "check" | "press" | "wait" => {
                let operation = request["operation"].as_str().ok_or("INVALID_REQUEST")?;
                let id = request["action_id"].as_str().ok_or("INVALID_ACTION_ID")?;
                let generation = request["generation"].as_str().ok_or("STALE_ACTION_ID")?;
                if generation != self.generation
                    || !id.starts_with(&(self.generation.clone() + ":"))
                {
                    return Err("STALE_ACTION_ID".into());
                }
                let value = &request["value"];
                if ["fill", "select", "press"].contains(&operation) && !value.is_string() {
                    return Err("INVALID_ARGUMENT".into());
                }
                if operation == "check" && !value.is_boolean() {
                    return Err("INVALID_ARGUMENT".into());
                }
                if value.as_str().is_some_and(|value| value.len() > 65536) {
                    return Err("REQUEST_TOO_LARGE".into());
                }
                let args =
                    json!({"id":id,"generation":generation,"operation":operation,"value":value});
                let result = self
                    .evaluate(format!("globalThis.__aeroState.perform({args})"))
                    .await?;
                if result["success"].as_bool() != Some(true) {
                    return Err(result["error"]["code"]
                        .as_str()
                        .unwrap_or("ACTION_FAILED")
                        .into());
                }
                self.live_snapshot().await
            }
            "scroll" => {
                let x = request["x"].as_i64().unwrap_or(0);
                let y = request["y"].as_i64().unwrap_or(600);
                if x.unsigned_abs() > 10000 || y.unsigned_abs() > 10000 {
                    return Err("INVALID_ARGUMENT".into());
                }
                self.evaluate(format!("window.scrollBy({x},{y});true"))
                    .await?;
                self.live_snapshot().await
            }
            "screenshot" => {
                let result = self
                    .call("Page.captureScreenshot", json!({"format":"png"}), true)
                    .await?;
                let encoded = result["data"].as_str().ok_or("SCREENSHOT_FAILED")?;
                if encoded.len() > MAX_BYTES * 2 {
                    return Err("RESPONSE_TOO_LARGE".into());
                }
                STANDARD.decode(encoded).map_err(|_| "SCREENSHOT_FAILED")?;
                Ok(json!({"success":true,"mime_type":"image/png","data":encoded}))
            }
            _ => Err("UNSUPPORTED_OPERATION".into()),
        }
    }
    async fn close(mut self) -> Result<(), String> {
        self.child
            .start_kill()
            .map_err(|_| "BROWSER_TERMINATION_FAILED")?;
        tokio::time::timeout(Duration::from_secs(5), self.child.wait())
            .await
            .map_err(|_| "BROWSER_TERMINATION_FAILED")?
            .map_err(|_| "BROWSER_TERMINATION_FAILED")?;
        Ok(())
    }
}

pub async fn run_session() -> Result<(), String> {
    let mut input = BufReader::new(tokio::io::stdin());
    let mut output = tokio::io::stdout();
    let mut browser: Option<FidelitySession> = None;
    loop {
        // An idle connection may stay open; partial frames have an absolute deadline.
        let mut first = [0_u8; 1];
        let count = input.read(&mut first).await.map_err(|_| "INPUT_CLOSED")?;
        if count == 0 {
            break;
        }
        let mut frame = vec![first[0]];
        if first[0] != b'\n' {
            tokio::time::timeout(
                Duration::from_secs(10),
                (&mut input).take(131072).read_until(b'\n', &mut frame),
            )
            .await
            .map_err(|_| "INPUT_TIMEOUT")?
            .map_err(|_| "INPUT_CLOSED")?;
        }
        if frame.len() > 131072 || frame.last() != Some(&b'\n') {
            return Err("REQUEST_TOO_LARGE".into());
        }
        let request: Value = match serde_json::from_slice(&frame) {
            Ok(value) => value,
            Err(_) => {
                output.write_all(b"{\"id\":null,\"success\":false,\"error\":{\"code\":\"INVALID_JSON\",\"message\":\"Invalid request\"}}\n").await.map_err(|_| "OUTPUT_CLOSED")?;
                continue;
            }
        };
        let id = request.get("id").cloned().unwrap_or(Value::Null);
        if !(id.is_u64() || id.as_str().is_some_and(|value| value.len() <= 128)) {
            return Err("INVALID_REQUEST_ID".into());
        }
        let result = if request["operation"].as_str() == Some("close") {
            if let Some(session) = browser.take() {
                session.close().await.map(|()| json!({"success":true}))
            } else {
                Ok(json!({"success":true}))
            }
        } else {
            if browser.is_none() {
                match FidelitySession::launch().await {
                    Ok(session) => browser = Some(session),
                    Err(code) => {
                        let response = json!({"id":id,"success":false,"error":{"code":code,"message":"Native browser unavailable"}});
                        output
                            .write_all(format!("{response}\n").as_bytes())
                            .await
                            .map_err(|_| "OUTPUT_CLOSED")?;
                        output.flush().await.map_err(|_| "OUTPUT_CLOSED")?;
                        continue;
                    }
                }
            }
            match browser.as_mut() {
                Some(session) => session.bounded(&request).await,
                None => Err("SESSION_CLOSED".into()),
            }
        };
        let mut response = match result {
            Ok(value) => value,
            Err(code) => {
                json!({"success":false,"error":{"code":code,"message":"Operation failed"}})
            }
        };
        response["id"] = id;
        let raw = format!("{response}\n");
        if raw.len() > FRAME_LIMIT {
            return Err("RESPONSE_TOO_LARGE".into());
        }
        tokio::time::timeout(Duration::from_secs(10), output.write_all(raw.as_bytes()))
            .await
            .map_err(|_| "OUTPUT_TIMEOUT")?
            .map_err(|_| "OUTPUT_CLOSED")?;
        output.flush().await.map_err(|_| "OUTPUT_CLOSED")?;
    }
    if let Some(session) = browser {
        session.close().await?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn shared_actions_require_exact_nodes_and_generation() {
        assert!(ACTION_RUNTIME.contains("state.nodes.get(args.id)"));
        assert!(ACTION_RUNTIME.contains("STALE_ACTION_ID"));
        assert!(!ACTION_RUNTIME.contains("data-aero-id"));
    }
}
