//! Bounded, DNS-pinned HTTP. No environment proxy, cookies or automatic redirects.
use crate::pruner::{PrunedResult, SemanticPruner};
use crate::security::{self, DEADLINE, MAX_BYTES};
use reqwest::redirect::Policy;
use serde::Serialize;
use std::time::Instant;

#[derive(Serialize)]
pub struct TurboResponse {
    pub pruned: PrunedResult,
    pub elapsed_ms: u128,
    pub needs_fidelity: bool,
    pub url: String,
    pub status_code: u16,
}

pub struct TurboEngine;
impl TurboEngine {
    pub fn new() -> Self {
        Self
    }

    pub async fn fetch(&self, input: &str) -> Result<TurboResponse, String> {
        tokio::time::timeout(DEADLINE, self.fetch_inner(input))
            .await
            .map_err(|_| "TIMEOUT".to_string())?
    }

    async fn fetch_inner(&self, input: &str) -> Result<TurboResponse, String> {
        let start = Instant::now();
        let mut url = security::parse_url(input)?;
        for hop in 0..=5 {
            let addresses = security::resolve(&url).await?;
            let host = url
                .host_str()
                .ok_or("INVALID_URL")?
                .trim_matches(['[', ']']);
            let client = reqwest::Client::builder()
                .no_proxy()
                .redirect(Policy::none())
                .timeout(DEADLINE)
                .connect_timeout(std::time::Duration::from_secs(5))
                .resolve_to_addrs(host, &addresses)
                .build()
                .map_err(|_| "TRANSPORT_ERROR")?;
            let mut response = client
                .get(url.clone())
                .header("Accept-Encoding", "identity")
                .send()
                .await
                .map_err(|_| "NETWORK_ERROR")?;
            if matches!(response.status().as_u16(), 301 | 302 | 303 | 307 | 308) {
                if hop == 5 {
                    return Err("TOO_MANY_REDIRECTS".into());
                }
                let location = response
                    .headers()
                    .get("location")
                    .ok_or("INVALID_REDIRECT")?
                    .to_str()
                    .map_err(|_| "INVALID_REDIRECT")?;
                let next = url.join(location).map_err(|_| "INVALID_REDIRECT")?;
                url = security::parse_url(next.as_str())?;
                continue;
            }
            let status_code = response.status().as_u16();
            if !response.status().is_success() {
                return Err("HTTP_ERROR".into());
            }
            if response
                .headers()
                .get("content-encoding")
                .is_some_and(|v| v != "identity")
            {
                return Err("UNSUPPORTED_ENCODING".into());
            }
            if response
                .content_length()
                .is_some_and(|n| n > MAX_BYTES as u64)
            {
                return Err("RESPONSE_TOO_LARGE".into());
            }
            let mut bytes = Vec::new();
            while let Some(chunk) = response.chunk().await.map_err(|_| "NETWORK_ERROR")? {
                if bytes.len() + chunk.len() > MAX_BYTES {
                    return Err("RESPONSE_TOO_LARGE".into());
                }
                bytes.extend_from_slice(&chunk);
            }
            let html = String::from_utf8_lossy(&bytes);
            let pruned = SemanticPruner::prune(&html, url.as_str())?;
            let lower = html.to_lowercase();
            let needs_fidelity = lower.contains("you need to enable javascript")
                || lower.contains("please enable js")
                || (pruned.markdown.split_whitespace().count() < 30
                    && [
                        "id=\"root\"",
                        "id=\"app\"",
                        "id=\"__next\"",
                        "ng-version",
                        "data-v-app",
                    ]
                    .iter()
                    .any(|s| lower.contains(s)));
            return Ok(TurboResponse {
                pruned,
                elapsed_ms: start.elapsed().as_millis(),
                needs_fidelity,
                url: url.to_string(),
                status_code,
            });
        }
        Err("TOO_MANY_REDIRECTS".into())
    }
}
