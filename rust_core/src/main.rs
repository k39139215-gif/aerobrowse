mod pruner;
mod turbo;
mod fidelity;
mod mcp;

use clap::{Parser, Subcommand};
use colored::*;
use turbo::TurboEngine;
use fidelity::FidelitySession;
use std::time::Instant;

const BANNER: &str = r#"
     _                     ____                                
    / \   ___ _ __ ___    | __ ) _ __ _____      _____  ___   
   / _ \ / _ \ '__/ _ \   |  _ \| '__/ _ \ \ /\ / / __|/ _ \  
  / ___ \  __/ | | (_) |  | |_) | | | (_) \ V  V /\__ \  __/  
 /_/   \_\___|_|  \___/   |____/|_|  \___/ \_/\_/ |___/\___|  
"#;

#[derive(Parser)]
#[command(name = "aerobrowse", author = "Kartik", version = "0.2.0", about = "Featherweight AI Browser Engine in Rust")]
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
        /// Force full Blink/V8 JavaScript execution via native CDP session
        #[arg(short, long)]
        fidelity: bool,
    },
    /// Click an element on a live page by Action ID
    Click {
        url: String,
        action_id: usize,
    },
    /// Fill an input field on a live page by Action ID
    Fill {
        url: String,
        action_id: usize,
        text: String,
    },
    /// Launch Model Context Protocol (MCP) server over stdio
    Mcp,
}

#[tokio::main]
async fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Fetch { url, fidelity } => {
            println!("{}", BANNER.cyan().bold());
            
            if fidelity {
                println!("{}", "⚡ AeroBrowse Native Rust Core — Fidelity Mode (100% JS / CDP)".magenta().bold());
                println!("\nLaunching Native CDP Session for: {}", url.yellow());
                let start = Instant::now();
                match FidelitySession::launch().await {
                    Ok(session) => {
                        match session.navigate(&url).await {
                            Ok(res) => {
                                let elapsed_ms = start.elapsed().as_millis();
                                print_telemetry(&res, elapsed_ms, "Fidelity (Blink/V8)");
                            }
                            Err(e) => eprintln!("{}: {}", "Navigation Error".red().bold(), e),
                        }
                    }
                    Err(e) => eprintln!("{}: {}", "CDP Launch Error".red().bold(), e),
                }
            } else {
                println!("{}", "⚡ AeroBrowse Native Rust Core — Turbo Mode (Sub-100ms)".green().bold());
                println!("\nFetching: {}", url.yellow());

                let engine = TurboEngine::new();
                match engine.fetch(&url).await {
                    Ok((res, elapsed_ms)) => {
                        print_telemetry(&res, elapsed_ms, "Turbo (Reqwest/AST)");
                    }
                    Err(e) => {
                        eprintln!("{}: {}", "Error".red().bold(), e);
                    }
                }
            }
        }
        Commands::Click { url, action_id } => {
            println!("{}", BANNER.cyan().bold());
            println!("Navigating to {} and clicking Action ID [{}]...", url.yellow(), action_id);
            match FidelitySession::launch().await {
                Ok(session) => {
                    let _ = session.navigate(&url).await;
                    match session.click(action_id).await {
                        Ok(msg) => println!("{}: {}", "Success".green().bold(), msg),
                        Err(e) => eprintln!("{}: {}", "Click Error".red().bold(), e),
                    }
                }
                Err(e) => eprintln!("{}: {}", "Browser Error".red().bold(), e),
            }
        }
        Commands::Fill { url, action_id, text } => {
            println!("{}", BANNER.cyan().bold());
            println!("Navigating to {} and typing into Action ID [{}]...", url.yellow(), action_id);
            match FidelitySession::launch().await {
                Ok(session) => {
                    let _ = session.navigate(&url).await;
                    match session.fill(action_id, &text).await {
                        Ok(msg) => println!("{}: {}", "Success".green().bold(), msg),
                        Err(e) => eprintln!("{}: {}", "Fill Error".red().bold(), e),
                    }
                }
                Err(e) => eprintln!("{}: {}", "Browser Error".red().bold(), e),
            }
        }
        Commands::Mcp => {
            if let Err(e) = mcp::run_mcp_server().await {
                eprintln!("MCP Error: {}", e);
            }
        }
    }
}

fn print_telemetry(res: &pruner::PrunedResult, elapsed_ms: u128, engine_name: &str) {
    println!("\n{}", "── Extraction Telemetry ──".green().bold());
    println!("Engine: {}", engine_name.bold());
    println!("Title: {}", res.title.bold());
    println!("Latency: {} ms", elapsed_ms);
    println!("Raw Size: {} bytes", res.original_chars);
    println!("Pruned Size: {} bytes", res.pruned_chars);
    println!("Token Savings: {}%", res.reduction_pct.to_string().green().bold());
    println!("Interactive Actions: {} mapped elements", res.actions.len());

    println!("\n{}", "── Clean Markdown Output ──".yellow().bold());
    println!("{}", res.markdown);

    if !res.actions.is_empty() {
        println!("\n{}", "── Top Action Elements ──".cyan().bold());
        for action in res.actions.iter().take(15) {
            let href = action.href.as_deref().unwrap_or("");
            println!("[{}] <{}> {} {}", action.id, action.tag.magenta(), action.label, href.dimmed());
        }
    }
}
