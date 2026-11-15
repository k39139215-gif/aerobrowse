mod pruner;
mod turbo;
mod mcp;

use clap::{Parser, Subcommand};
use colored::*;
use turbo::TurboEngine;

const BANNER: &str = r#"
     _                     ____                                
    / \   ___ _ __ ___    | __ ) _ __ _____      _____  ___   
   / _ \ / _ \ '__/ _ \   |  _ \| '__/ _ \ \ /\ / / __|/ _ \  
  / ___ \  __/ | | (_) |  | |_) | | | (_) \ V  V /\__ \  __/  
 /_/   \_\___|_|  \___/   |____/|_|  \___/ \_/\_/ |___/\___|  
"#;

#[derive(Parser)]
#[command(name = "aerobrowse", author = "Kartik", version = "0.1.0", about = "Featherweight AI Browser Engine in Rust")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Fetch URL, prune tokens, and output clean markdown
    Fetch {
        /// Target URL to browse
        url: String,
    },
    /// Launch Model Context Protocol (MCP) server over stdio
    Mcp,
}

#[tokio::main]
async fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Fetch { url } => {
            println!("{}", BANNER.cyan().bold());
            println!("{}", "⚡ AeroBrowse Native Rust Core — Sub-50ms Execution".dimmed());
            println!("\nFetching: {}", url.yellow());

            let engine = TurboEngine::new();
            match engine.fetch(&url).await {
                Ok((res, elapsed_ms)) => {
                    println!("\n{}", "── Extraction Telemetry ──".green().bold());
                    println!("Title: {}", res.title.bold());
                    println!("Latency: {} ms", elapsed_ms);
                    println!("Raw Size: {} bytes", res.original_chars);
                    println!("Pruned Size: {} bytes", res.pruned_chars);
                    println!("Token Savings: {}%", res.reduction_pct.to_string().green().bold());
                    println!("Interactive Actions: {} mapped elements", res.actions.len());

                    println!("\n{}", "── Markdown Output ──".yellow().bold());
                    println!("{}", res.markdown);

                    if !res.actions.is_empty() {
                        println!("\n{}", "── Top Action Elements ──".cyan().bold());
                        for action in res.actions.iter().take(15) {
                            let href = action.href.as_deref().unwrap_or("");
                            println!("[{}] <{}> {} {}", action.id, action.tag.magenta(), action.label, href.dimmed());
                        }
                    }
                }
                Err(e) => {
                    eprintln!("{}: {}", "Error".red().bold(), e);
                }
            }
        }
        Commands::Mcp => {
            if let Err(e) = mcp::run_mcp_server().await {
                eprintln!("MCP Error: {}", e);
            }
        }
    }
}
