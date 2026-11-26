//! One-hop broker: actual sockets use only validated, pinned addresses.
use crate::security::{self, DEADLINE, MAX_BYTES};
use base64::{engine::general_purpose::STANDARD, Engine};
use ipnet::IpNet;
use reqwest::{redirect::Policy, Method};
use serde_json::{json, Value};
use std::net::{IpAddr, SocketAddr};

pub struct NetworkPolicy {
    allowed: Vec<IpNet>,
}
impl NetworkPolicy {
    #[cfg(target_os = "linux")]
    pub fn from_environment() -> Result<Self, String> {
        let raw = std::env::var("AEROBROWSE_NATIVE_ALLOW_NETWORKS").unwrap_or_default();
        if raw.len() > 4096 {
            return Err("INVALID_RUNTIME_CONFIG".into());
        }
        let allowed = raw
            .split(',')
            .filter(|s| !s.is_empty())
            .map(|s| s.parse().map_err(|_| "INVALID_RUNTIME_CONFIG".to_string()))
            .collect::<Result<Vec<IpNet>, _>>()?;
        Ok(Self { allowed })
    }
    pub fn parse(&self, raw: &str) -> Result<url::Url, String> {
        // Syntax checks are identical to native Turbo. Only explicit operator CIDRs
        // can permit a destination which the public policy would reject.
        match security::parse_url(raw) {
            Ok(url) => Ok(url),
            Err(code) if code == "BLOCKED_DESTINATION" => {
                let url = url::Url::parse(raw).map_err(|_| "INVALID_URL")?;
                let host = url
                    .host_str()
                    .ok_or("INVALID_URL")?
                    .trim_matches(['[', ']']);
                let ip = host.parse::<IpAddr>().map_err(|_| "BLOCKED_DESTINATION")?;
                if self.allowed.iter().any(|network| network.contains(&ip)) {
                    Ok(url)
                } else {
                    Err(code)
                }
            }
            Err(code) => Err(code),
        }
    }
    fn permitted(&self, ip: IpAddr) -> bool {
        security::public_ip(ip) || self.allowed.iter().any(|network| network.contains(&ip))
    }
    async fn addresses(&self, url: &url::Url) -> Result<Vec<SocketAddr>, String> {
        let host = url
            .host_str()
            .ok_or("INVALID_URL")?
            .trim_matches(['[', ']']);
        let port = url.port_or_known_default().ok_or("INVALID_URL")?;
        let addresses = if let Ok(ip) = host.parse::<IpAddr>() {
            vec![SocketAddr::new(ip, port)]
        } else {
            tokio::net::lookup_host((host, port))
                .await
                .map_err(|_| "DNS_ERROR")?
                .collect()
        };
        if addresses.is_empty() {
            return Err("DNS_ERROR".into());
        }
        if !addresses.iter().all(|address| self.permitted(address.ip())) {
            return Err("BLOCKED_DESTINATION".into());
        }
        Ok(addresses)
    }
    pub async fn fulfill(&self, event: &Value) -> Result<Value, String> {
        tokio::time::timeout(DEADLINE, self.exchange(event))
            .await
            .map_err(|_| "TIMEOUT".to_string())?
    }
    async fn exchange(&self, event: &Value) -> Result<Value, String> {
        let request = event.get("request").ok_or("INVALID_REQUEST")?;
        let url = self.parse(request["url"].as_str().ok_or("INVALID_URL")?)?;
        let addresses = self.addresses(&url).await?;
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
        let method = request["method"].as_str().ok_or("INVALID_REQUEST")?;
        if !["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"].contains(&method) {
            return Err("INVALID_REQUEST".into());
        }
        let body = if let Some(entries) = request["postDataEntries"].as_array() {
            let mut body = Vec::new();
            for entry in entries {
                let encoded = entry["bytes"].as_str().ok_or("INVALID_REQUEST")?;
                if encoded.len() > MAX_BYTES * 2 {
                    return Err("REQUEST_TOO_LARGE".into());
                }
                let bytes = STANDARD.decode(encoded).map_err(|_| "INVALID_REQUEST")?;
                if body.len() + bytes.len() > MAX_BYTES {
                    return Err("REQUEST_TOO_LARGE".into());
                }
                body.extend(bytes);
            }
            body
        } else if let Some(text) = request["postData"].as_str() {
            text.as_bytes().to_vec()
        } else if request["hasPostData"].as_bool() == Some(true) {
            return Err("UNSUPPORTED_CAPABILITY".into());
        } else {
            Vec::new()
        };
        if body.len() > MAX_BYTES {
            return Err("REQUEST_TOO_LARGE".into());
        }
        let mut outgoing = client
            .request(
                Method::from_bytes(method.as_bytes()).map_err(|_| "INVALID_REQUEST")?,
                url.clone(),
            )
            .header("Accept-Encoding", "identity");
        if let Some(headers) = request["headers"].as_object() {
            if headers.len() > 128 {
                return Err("INVALID_REQUEST".into());
            }
            for (name, value) in headers {
                let name = name.to_ascii_lowercase();
                if [
                    "accept",
                    "accept-language",
                    "content-type",
                    "user-agent",
                    "cookie",
                    "origin",
                    "referer",
                    "sec-fetch-site",
                    "sec-fetch-mode",
                    "sec-fetch-dest",
                    "sec-fetch-user",
                ]
                .contains(&name.as_str())
                {
                    let value = value.as_str().ok_or("INVALID_REQUEST")?;
                    if value.len() > 8192 || value.contains(['\r', '\n', '\0']) {
                        return Err("INVALID_REQUEST".into());
                    }
                    outgoing = outgoing.header(&name, value);
                }
            }
        }
        let mut response = outgoing
            .body(body)
            .send()
            .await
            .map_err(|_| "NETWORK_ERROR")?;
        if response
            .content_length()
            .is_some_and(|n| n > MAX_BYTES as u64)
        {
            return Err("RESPONSE_TOO_LARGE".into());
        }
        if response
            .headers()
            .get("content-encoding")
            .is_some_and(|v| v != "identity")
        {
            return Err("UNSUPPORTED_ENCODING".into());
        }
        if matches!(response.status().as_u16(), 301 | 302 | 303 | 307 | 308) {
            let next = response
                .headers()
                .get("location")
                .ok_or("INVALID_REDIRECT")?
                .to_str()
                .map_err(|_| "INVALID_REDIRECT")?;
            let next = url.join(next).map_err(|_| "INVALID_REDIRECT")?;
            let checked = self.parse(next.as_str())?;
            self.addresses(&checked).await?;
        }
        let mut headers = Vec::new();
        let mut header_bytes = 0;
        for (name, value) in response.headers() {
            if [
                "content-length",
                "transfer-encoding",
                "connection",
                "content-encoding",
                "authorization",
                "proxy-authorization",
            ]
            .contains(&name.as_str())
            {
                continue;
            }
            let value = value.to_str().map_err(|_| "INVALID_RESPONSE")?;
            header_bytes += name.as_str().len() + value.len();
            if header_bytes > 32768 {
                return Err("INVALID_RESPONSE".into());
            }
            headers.push(json!({"name":name.as_str(), "value":value}));
        }
        let status = response.status().as_u16();
        let mut body = Vec::new();
        while let Some(chunk) = response.chunk().await.map_err(|_| "NETWORK_ERROR")? {
            if body.len() + chunk.len() > MAX_BYTES {
                return Err("RESPONSE_TOO_LARGE".into());
            }
            body.extend_from_slice(&chunk);
        }
        Ok(
            json!({"requestId":event["requestId"], "responseCode":status,"responseHeaders":headers,"body":STANDARD.encode(body)}),
        )
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn defaults_deny_private_and_explicit_cidrs_are_narrow() {
        let policy = NetworkPolicy { allowed: vec![] };
        for url in [
            "http://127.0.0.1",
            "http://[::1]",
            "http://169.254.169.254",
            "file:///etc/passwd",
            "http://2130706433",
        ] {
            assert!(policy.parse(url).is_err());
        }
        let policy = NetworkPolicy {
            allowed: vec!["127.0.0.1/32".parse().expect("test network")],
        };
        assert!(policy.parse("http://127.0.0.1/a").is_ok());
        for url in [
            "http://127.0.0.2",
            "http://user:secret@127.0.0.1",
            "http://127.0.0.1/\n",
        ] {
            assert!(policy.parse(url).is_err());
        }
    }
}
