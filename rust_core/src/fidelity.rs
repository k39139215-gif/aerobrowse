//! Native CDP is deliberately unavailable until an enforceable OS network boundary exists.
//! This is an explicit security restriction, not a mock browser implementation.
use crate::pruner::PrunedResult;
pub struct FidelitySession;
impl FidelitySession {
    pub async fn launch() -> Result<Self, String> {
        Err("NETWORK_ISOLATION_UNAVAILABLE: native Rust Fidelity is disabled; use isolated Python Fidelity".into())
    }
    pub async fn navigate(&self, _url: &str) -> Result<PrunedResult, String> {
        Err("NETWORK_ISOLATION_UNAVAILABLE".into())
    }
    pub async fn click(&self, _action_id: usize) -> Result<String, String> {
        Err("UNSUPPORTED_OPERATION".into())
    }
    pub async fn fill(&self, _action_id: usize, _text: &str) -> Result<String, String> {
        Err("UNSUPPORTED_OPERATION".into())
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[tokio::test]
    async fn cannot_start_unrestricted_browser_or_execute_values() {
        assert!(FidelitySession::launch().await.is_err());
        let session = FidelitySession;
        assert!(session
            .fill(1, "\\\";globalThis.secret=1;//")
            .await
            .is_err());
        assert!(session.click(1).await.is_err());
    }
}
