//! Use the official Python MCP server, preserving protocol/session/security parity.
//! Native read-only retrieval remains available without Python. This command requires
//! the installed Python SDK and explicitly reports a missing runtime.
use std::io;
use std::process::Stdio;
use tokio::process::Command;

pub async fn run_mcp_server() -> io::Result<()> {
    let status = Command::new("python")
        .args(["-m", "aerobrowse.mcp_server"])
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .kill_on_drop(true)
        .status()
        .await?;
    if status.success() {
        Ok(())
    } else {
        Err(io::Error::other("MCP_RUNTIME_FAILED"))
    }
}
