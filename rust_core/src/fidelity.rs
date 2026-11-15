use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};
use futures_util::{SinkExt, StreamExt};
use serde_json::{json, Value};
use tokio_tungstenite::connect_async;
use tokio_tungstenite::tungstenite::Message;

use crate::pruner::{PrunedResult, SemanticPruner};

pub struct FidelitySession {
    child: Option<Child>,
    port: u16,
    ws_url: String,
    temp_dir: PathBuf,
}

impl FidelitySession {
    /// Discovers system-installed Chrome or Edge binary
    pub fn find_browser() -> Option<PathBuf> {
        #[cfg(target_os = "windows")]
        {
            let candidates = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ];
            for path in candidates {
                let p = PathBuf::from(path);
                if p.exists() {
                    return Some(p);
                }
            }
        }

        #[cfg(target_os = "linux")]
        {
            let candidates = [
                "/usr/bin/google-chrome",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium",
            ];
            for path in candidates {
                let p = PathBuf::from(path);
                if p.exists() {
                    return Some(p);
                }
            }
        }

        #[cfg(target_os = "macos")]
        {
            let candidates = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
            ];
            for path in candidates {
                let p = PathBuf::from(path);
                if p.exists() {
                    return Some(p);
                }
            }
        }

        None
    }

    /// Spawns a lightweight native headless Chromium/Edge instance with CDP
    pub async fn launch() -> Result<Self, String> {
        let browser_path = Self::find_browser()
            .ok_or_else(|| "No supported Chromium or Edge browser found on this system.".to_string())?;

        // Pick a dynamic port based on process ID to avoid collisions
        let port = 9300 + (std::process::id() % 500) as u16;
        let temp_dir = std::env::temp_dir().join(format!("aerobrowse_profile_{}", port));
        let _ = std::fs::create_dir_all(&temp_dir);

        let child = Command::new(&browser_path)
            .arg("--headless=new")
            .arg(format!("--remote-debugging-port={}", port))
            .arg("--remote-allow-origins=*")
            .arg("--disable-gpu")
            .arg("--no-first-run")
            .arg("--no-default-browser-check")
            .arg("--disable-extensions")
            .arg("--disable-background-networking")
            .arg("--blink-settings=imagesEnabled=false") // Strips heavy images inside Blink
            .arg(format!("--user-data-dir={}", temp_dir.to_string_lossy()))
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("Failed to spawn browser process: {}", e))?;

        // Wait for CDP readiness (up to 4s)
        let client = reqwest::Client::new();
        let version_url = format!("http://127.0.0.1:{}/json/version", port);
        let start = Instant::now();
        let mut ready = false;

        while start.elapsed() < Duration::from_secs(4) {
            if client.get(&version_url).send().await.is_ok() {
                ready = true;
                break;
            }
            tokio::time::sleep(Duration::from_millis(50)).await;
        }

        if !ready {
            return Err("Timed out waiting for browser CDP interface to start.".to_string());
        }

        // Open a new tab via /json/new
        let new_tab_url = format!("http://127.0.0.1:{}/json/new", port);
        let tab_resp = client.put(&new_tab_url).send().await
            .map_err(|e| format!("Failed to create new CDP tab: {}", e))?
            .json::<Value>().await
            .map_err(|e| format!("Invalid tab JSON: {}", e))?;

        let ws_url = tab_resp.get("webSocketDebuggerUrl")
            .and_then(|v| v.as_str())
            .ok_or_else(|| "Missing webSocketDebuggerUrl in CDP response".to_string())?
            .to_string();

        Ok(Self {
            child: Some(child),
            port,
            ws_url,
            temp_dir,
        })
    }

    /// Navigates to URL, executes client-side JavaScript, and prunes content with full fidelity
    pub async fn navigate(&self, url: &str) -> Result<PrunedResult, String> {
        let (mut ws, _) = connect_async(&self.ws_url).await
            .map_err(|e| format!("Failed to connect to browser WebSocket: {}", e))?;

        // 1. Enable Page & Runtime domains
        let enable_msg = json!({
            "id": 1,
            "method": "Page.enable"
        });
        ws.send(Message::Text(enable_msg.to_string())).await
            .map_err(|e| format!("WS Send error: {}", e))?;

        // 2. Navigate to target URL
        let nav_msg = json!({
            "id": 2,
            "method": "Page.navigate",
            "params": {
                "url": url
            }
        });
        ws.send(Message::Text(nav_msg.to_string())).await
            .map_err(|e| format!("WS Send error: {}", e))?;

        // 3. Wait for Page.loadEventFired or timeout (max 6s)
        let load_start = Instant::now();
        while load_start.elapsed() < Duration::from_secs(6) {
            if let Some(Ok(Message::Text(text))) = ws.next().await {
                if let Ok(val) = serde_json::from_str::<Value>(&text) {
                    if val.get("method").and_then(|m| m.as_str()) == Some("Page.loadEventFired") {
                        break;
                    }
                }
            }
        }

        // Stabilization delay for dynamic SPA rendering (React 19 / Vue / Next.js)
        tokio::time::sleep(Duration::from_millis(250)).await;

        // 4. Extract rendered HTML via Runtime.evaluate
        let eval_msg = json!({
            "id": 3,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "document.documentElement.outerHTML"
            }
        });
        ws.send(Message::Text(eval_msg.to_string())).await
            .map_err(|e| format!("WS Send error: {}", e))?;

        let mut html = String::new();
        while let Some(Ok(Message::Text(text))) = ws.next().await {
            if let Ok(val) = serde_json::from_str::<Value>(&text) {
                if val.get("id").and_then(|id| id.as_i64()) == Some(3) {
                    if let Some(rendered) = val.get("result")
                        .and_then(|r| r.get("result"))
                        .and_then(|res| res.get("value"))
                        .and_then(|v| v.as_str()) {
                        html = rendered.to_string();
                        break;
                    }
                }
            }
        }

        let _ = ws.close(None).await;

        if html.is_empty() {
            return Err("Failed to retrieve rendered HTML from browser.".to_string());
        }

        // 5. Run Semantic Token Pruning & Action Mapping
        Ok(SemanticPruner::prune(&html, url))
    }

    /// Simulates clicking an interactive element by Action ID or CSS selector
    pub async fn click(&self, action_id: usize) -> Result<String, String> {
        let (mut ws, _) = connect_async(&self.ws_url).await
            .map_err(|e| format!("Failed to connect to browser WebSocket: {}", e))?;

        let js_click = format!(
            r#"(() => {{
                let el = document.querySelector('[data-aero-id="{}"]') || document.querySelectorAll('button, a, input')[{} - 1];
                if (el) {{
                    el.click();
                    return "Clicked: " + (el.innerText || el.value || el.tagName);
                }}
                return "Element not found";
            }})()"#,
            action_id, action_id
        );

        let eval_msg = json!({
            "id": 10,
            "method": "Runtime.evaluate",
            "params": {
                "expression": js_click
            }
        });

        ws.send(Message::Text(eval_msg.to_string())).await
            .map_err(|e| format!("WS Send error: {}", e))?;

        let mut result = "Click dispatched".to_string();
        while let Some(Ok(Message::Text(text))) = ws.next().await {
            if let Ok(val) = serde_json::from_str::<Value>(&text) {
                if val.get("id").and_then(|id| id.as_i64()) == Some(10) {
                    if let Some(res) = val.get("result")
                        .and_then(|r| r.get("result"))
                        .and_then(|v| v.get("value"))
                        .and_then(|s| s.as_str()) {
                        result = res.to_string();
                        break;
                    }
                }
            }
        }

        let _ = ws.close(None).await;
        Ok(result)
    }

    /// Simulates typing into an input field by Action ID
    pub async fn fill(&self, action_id: usize, text_to_type: &str) -> Result<String, String> {
        let (mut ws, _) = connect_async(&self.ws_url).await
            .map_err(|e| format!("Failed to connect to browser WebSocket: {}", e))?;

        let escaped_text = text_to_type.replace('"', "\\\"");
        let js_fill = format!(
            r#"(() => {{
                let el = document.querySelector('[data-aero-id="{}"]') || document.querySelectorAll('input, textarea')[{} - 1];
                if (el) {{
                    el.value = "{}";
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return "Filled input: " + el.value;
                }}
                return "Input element not found";
            }})()"#,
            action_id, action_id, escaped_text
        );

        let eval_msg = json!({
            "id": 11,
            "method": "Runtime.evaluate",
            "params": {
                "expression": js_fill
            }
        });

        ws.send(Message::Text(eval_msg.to_string())).await
            .map_err(|e| format!("WS Send error: {}", e))?;

        let mut result = "Fill dispatched".to_string();
        while let Some(Ok(Message::Text(text))) = ws.next().await {
            if let Ok(val) = serde_json::from_str::<Value>(&text) {
                if val.get("id").and_then(|id| id.as_i64()) == Some(11) {
                    if let Some(res) = val.get("result")
                        .and_then(|r| r.get("result"))
                        .and_then(|v| v.get("value"))
                        .and_then(|s| s.as_str()) {
                        result = res.to_string();
                        break;
                    }
                }
            }
        }

        let _ = ws.close(None).await;
        Ok(result)
    }
}

impl Drop for FidelitySession {
    fn drop(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
        }
        let _ = std::fs::remove_dir_all(&self.temp_dir);
    }
}
