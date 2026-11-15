use std::io::{self, BufRead, Write};
use serde_json::{json, Value};
use crate::turbo::TurboEngine;
use crate::fidelity::FidelitySession;

pub async fn run_mcp_server() -> io::Result<()> {
    let engine = TurboEngine::new();
    let stdin = io::stdin();
    let mut stdout = io::stdout();

    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };

        if line.trim().is_empty() {
            continue;
        }

        let req: Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(_) => continue,
        };

        let id = req.get("id").cloned().unwrap_or(Value::Null);
        let method = req.get("method").and_then(|m| m.as_str()).unwrap_or("");

        let response = match method {
            "initialize" => json!({
                "jsonrpc": "2.0",
                "id": id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": { "tools": {} },
                    "serverInfo": {
                        "name": "AeroBrowse-Rust",
                        "version": "0.2.0"
                    }
                }
            }),
            "tools/list" => json!({
                "jsonrpc": "2.0",
                "id": id,
                "result": {
                    "tools": [
                        {
                            "name": "browser_navigate",
                            "description": "Navigate to any URL and return token-dense Markdown with Action IDs. Optionally force JavaScript rendering.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "url": { "type": "string" },
                                    "force_fidelity": { "type": "boolean", "description": "Set true for complex SPAs requiring JavaScript" }
                                },
                                "required": ["url"]
                            }
                        },
                        {
                            "name": "browser_click",
                            "description": "Click an interactive element on the page by its numeric Action ID",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "url": { "type": "string" },
                                    "action_id": { "type": "integer" }
                                },
                                "required": ["url", "action_id"]
                            }
                        },
                        {
                            "name": "browser_fill",
                            "description": "Type text into an input field by its numeric Action ID",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "url": { "type": "string" },
                                    "action_id": { "type": "integer" },
                                    "value": { "type": "string" }
                                },
                                "required": ["url", "action_id", "value"]
                            }
                        }
                    ]
                }
            }),
            "tools/call" => {
                let params = req.get("params").cloned().unwrap_or_default();
                let tool_name = params.get("name").and_then(|n| n.as_str()).unwrap_or("");
                let args = params.get("arguments").cloned().unwrap_or_default();

                match tool_name {
                    "browser_navigate" => {
                        let url = args.get("url").and_then(|u| u.as_str()).unwrap_or("");
                        let force_fidelity = args.get("force_fidelity").and_then(|f| f.as_bool()).unwrap_or(false);

                        if force_fidelity {
                            match FidelitySession::launch().await {
                                Ok(session) => match session.navigate(url).await {
                                    Ok(res) => {
                                        let text = format!(
                                            "# {}\nURL: {}\nEngine: Fidelity (Blink/V8) | Token Reduction: {}%\n\n{}\n\nActions Found: {}",
                                            res.title, url, res.reduction_pct, res.markdown, res.actions.len()
                                        );
                                        json!({
                                            "jsonrpc": "2.0",
                                            "id": id,
                                            "result": {
                                                "content": [{ "type": "text", "text": text }]
                                            }
                                        })
                                    }
                                    Err(e) => json!({
                                        "jsonrpc": "2.0",
                                        "id": id,
                                        "error": { "code": -32000, "message": e }
                                    }),
                                },
                                Err(e) => json!({
                                    "jsonrpc": "2.0",
                                    "id": id,
                                    "error": { "code": -32000, "message": e }
                                }),
                            }
                        } else {
                            match engine.fetch(url).await {
                                Ok((res, ms)) => {
                                    let text = format!(
                                        "# {}\nURL: {}\nLatency: {}ms | Token Reduction: {}%\n\n{}\n\nActions Found: {}",
                                        res.title, url, ms, res.reduction_pct, res.markdown, res.actions.len()
                                    );
                                    json!({
                                        "jsonrpc": "2.0",
                                        "id": id,
                                        "result": {
                                            "content": [{ "type": "text", "text": text }]
                                        }
                                    })
                                }
                                Err(e) => json!({
                                    "jsonrpc": "2.0",
                                    "id": id,
                                    "error": { "code": -32000, "message": e }
                                }),
                            }
                        }
                    }
                    "browser_click" => {
                        let url = args.get("url").and_then(|u| u.as_str()).unwrap_or("");
                        let action_id = args.get("action_id").and_then(|a| a.as_u64()).unwrap_or(1) as usize;

                        match FidelitySession::launch().await {
                            Ok(session) => {
                                let _ = session.navigate(url).await;
                                match session.click(action_id).await {
                                    Ok(msg) => json!({
                                        "jsonrpc": "2.0",
                                        "id": id,
                                        "result": {
                                            "content": [{ "type": "text", "text": msg }]
                                        }
                                    }),
                                    Err(e) => json!({
                                        "jsonrpc": "2.0",
                                        "id": id,
                                        "error": { "code": -32000, "message": e }
                                    }),
                                }
                            }
                            Err(e) => json!({
                                "jsonrpc": "2.0",
                                "id": id,
                                "error": { "code": -32000, "message": e }
                            }),
                        }
                    }
                    "browser_fill" => {
                        let url = args.get("url").and_then(|u| u.as_str()).unwrap_or("");
                        let action_id = args.get("action_id").and_then(|a| a.as_u64()).unwrap_or(1) as usize;
                        let value = args.get("value").and_then(|v| v.as_str()).unwrap_or("");

                        match FidelitySession::launch().await {
                            Ok(session) => {
                                let _ = session.navigate(url).await;
                                match session.fill(action_id, value).await {
                                    Ok(msg) => json!({
                                        "jsonrpc": "2.0",
                                        "id": id,
                                        "result": {
                                            "content": [{ "type": "text", "text": msg }]
                                        }
                                    }),
                                    Err(e) => json!({
                                        "jsonrpc": "2.0",
                                        "id": id,
                                        "error": { "code": -32000, "message": e }
                                    }),
                                }
                            }
                            Err(e) => json!({
                                "jsonrpc": "2.0",
                                "id": id,
                                "error": { "code": -32000, "message": e }
                            }),
                        }
                    }
                    _ => json!({
                        "jsonrpc": "2.0",
                        "id": id,
                        "error": { "code": -32601, "message": "Method not found" }
                    }),
                }
            }
            _ => json!({
                "jsonrpc": "2.0",
                "id": id,
                "result": {}
            }),
        };

        let out_str = serde_json::to_string(&response).unwrap();
        writeln!(stdout, "{}", out_str)?;
        stdout.flush()?;
    }

    Ok(())
}
