//! Structured CLI output. Native browser commands fail closed, never report a fallback success.
mod fidelity;
mod mcp;
mod native_browser;
mod native_network;
mod pruner;
mod security;
mod turbo;

use clap::{Parser, Subcommand};
use serde_json::json;
use std::process::ExitCode;
use turbo::TurboEngine;

#[derive(Parser)]
#[command(
    name = "aerobrowse",
    version,
    about = "Bounded HTTP retrieval and owned MCP browser sessions"
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}
#[derive(Subcommand)]
enum Commands {
    Fetch {
        url: String,
        #[arg(short, long)]
        fidelity: bool,
    },
    Click {
        url: String,
        action_id: usize,
    },
    Fill {
        url: String,
        action_id: usize,
        text: String,
    },
    /// Persistent correlated native browser session over bounded newline JSON.
    NativeSession,
    Mcp,
}

#[tokio::main]
async fn main() -> ExitCode {
    let result = match Cli::parse().command {
        Commands::Fetch { url, fidelity } => {
            if fidelity {
                match fidelity::FidelitySession::launch().await {
                    Err(code) => Err(code),
                    Ok(mut session) => session.navigate(&url).await.and_then(|v| {
                        serde_json::to_value(v).map_err(|_| "SERIALIZATION_ERROR".into())
                    }),
                }
            } else {
                TurboEngine::new().fetch(&url).await.and_then(|value| {
                    if value.needs_fidelity {
                        return Err("FIDELITY_REQUIRED: use the isolated Python engine".into());
                    }
                    serde_json::to_value(value).map_err(|_| "SERIALIZATION_ERROR".into())
                })
            }
        }
        Commands::Click { url, action_id } => {
            if let Err(code) = security::parse_url(&url) {
                Err(code)
            } else {
                let _ = action_id;
                Err("STALE_ACTION_ID: use native-session with a live generation".into())
            }
        }
        Commands::Fill {
            url,
            action_id,
            text,
        } => {
            if let Err(code) = security::parse_url(&url) {
                Err(code)
            } else {
                let _ = (action_id, text);
                Err("STALE_ACTION_ID: use native-session with a live generation".into())
            }
        }
        Commands::NativeSession => {
            return if fidelity::run_session().await.is_ok() {
                ExitCode::SUCCESS
            } else {
                ExitCode::FAILURE
            };
        }
        Commands::Mcp => {
            return if mcp::run_mcp_server().await.is_ok() {
                ExitCode::SUCCESS
            } else {
                eprintln!("MCP_RUNTIME_FAILED: install the Python AeroBrowse SDK");
                ExitCode::FAILURE
            }
        }
    };
    match result {
        Ok(value) => {
            println!("{}", json!({"success":true,"result":value}));
            ExitCode::SUCCESS
        }
        Err(code) => {
            println!(
                "{}",
                json!({"success":false,"error":{"code":code,"message":"Operation failed"}})
            );
            ExitCode::FAILURE
        }
    }
}
