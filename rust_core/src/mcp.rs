use std::io::{self, BufRead, Write};
use serde_json::{json, Value};
use crate::turbo::TurboEngine;

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
                        "version": "0.1.0"
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
                            "description": "Navigate to any URL and return token-dense Markdown with Action IDs",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "url": { "type": "string" }
                                },
                                "required": ["url"]
                            }
                        }
                    ]
                }
            }),
            "tools/call" => {
                let params = req.get("params").cloned().unwrap_or_default();
                let tool_name = params.get("name").and_then(|n| n.as_str()).unwrap_or("");
                let args = params.get("arguments").cloned().unwrap_or_default();

                if tool_name == "browser_navigate" {
                    let url = args.get("url").and_then(|u| u.as_str()).unwrap_or("");
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
                } else {
                    json!({
                        "jsonrpc": "2.0",
                        "id": id,
                        "error": { "code": -32601, "message": "Method not found" }
                    })
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
