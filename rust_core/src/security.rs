//! URL policy for every Rust network entry. Connection resolution is pinned in Turbo.
use std::net::{IpAddr, SocketAddr};
use std::time::Duration;
use url::{Host, Url};

pub const MAX_BYTES: usize = 4 * 1024 * 1024;
pub const DEADLINE: Duration = Duration::from_secs(20);

pub fn public_ip(ip: IpAddr) -> bool {
    match ip {
        IpAddr::V4(a) => {
            let [x, y, z, _] = a.octets();
            !(x == 0
                || x == 10
                || x == 127
                || x >= 224
                || (x == 100 && (64..=127).contains(&y))
                || (x == 169 && y == 254)
                || (x == 172 && (16..=31).contains(&y))
                || (x == 192 && (y == 168 || y == 0 || (y == 88 && z == 99)))
                || (x == 198 && (y == 18 || y == 19 || (y == 51 && z == 100)))
                || (x == 203 && y == 0 && z == 113))
        }
        IpAddr::V6(a) => {
            // Conservative public unicast only, excluding transition/documentation ranges.
            let s = a.segments();
            (s[0] & 0xe000) == 0x2000
                && !(s[0] == 0x2001 && (s[1] < 0x200 || s[1] == 0xdb8))
                && s[0] != 0x2002
                && !(s[0] == 0x3fff && s[1] < 0x1000)
        }
    }
}

pub fn parse_url(input: &str) -> Result<Url, String> {
    if input.is_empty()
        || input.len() > 8192
        || input
            .chars()
            .any(|c| c.is_control() || c.is_whitespace() || c == '\\')
    {
        return Err("INVALID_URL".into());
    }
    let mut url = Url::parse(input).map_err(|_| "INVALID_URL")?;
    if !matches!(url.scheme(), "http" | "https")
        || !url.username().is_empty()
        || url.password().is_some()
        || url.port_or_known_default().is_none()
    {
        return Err("INVALID_URL".into());
    }
    let host = url
        .host_str()
        .ok_or("INVALID_URL")?
        .trim_end_matches('.')
        .to_lowercase();
    match url.host().ok_or("INVALID_URL")? {
        Host::Ipv4(a) => {
            if !public_ip(IpAddr::V4(a)) {
                return Err("BLOCKED_DESTINATION".into());
            }
        }
        Host::Ipv6(a) => {
            if !public_ip(IpAddr::V6(a)) {
                return Err("BLOCKED_DESTINATION".into());
            }
        }
        Host::Domain(_) => {
            if !host.contains('.')
                || [".localhost", ".local", ".internal", ".home", ".lan"]
                    .iter()
                    .any(|suffix| host.ends_with(suffix))
            {
                return Err("BLOCKED_DESTINATION".into());
            }
        }
    }
    url.set_fragment(None);
    Ok(url)
}

pub async fn resolve(url: &Url) -> Result<Vec<SocketAddr>, String> {
    let host = url
        .host_str()
        .ok_or("INVALID_URL")?
        .trim_matches(['[', ']']);
    let port = url.port_or_known_default().ok_or("INVALID_URL")?;
    let addresses: Vec<_> = match url.host().ok_or("INVALID_URL")? {
        Host::Ipv4(a) => vec![SocketAddr::new(IpAddr::V4(a), port)],
        Host::Ipv6(a) => vec![SocketAddr::new(IpAddr::V6(a), port)],
        Host::Domain(_) => tokio::net::lookup_host((host, port))
            .await
            .map_err(|_| "DNS_ERROR")?
            .collect(),
    };
    if addresses.is_empty() {
        return Err("DNS_ERROR".into());
    }
    if addresses.iter().any(|a| !public_ip(a.ip())) {
        return Err("BLOCKED_DESTINATION".into());
    }
    Ok(addresses)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::{Ipv4Addr, Ipv6Addr};
    #[test]
    fn blocked_networks_and_schemes() {
        for url in [
            "http://127.0.0.1",
            "http://2130706433",
            "http://0x7f000001",
            "http://10.1.1.1",
            "http://172.16.1.1",
            "http://192.168.1.1",
            "http://169.254.169.254",
            "http://[::1]",
            "http://[fc00::1]",
            "http://[fe80::1]",
            "http://[::ffff:127.0.0.1]",
            "http://[64:ff9b::7f00:1]",
            "http://0.0.0.0",
            "http://224.0.0.1",
            "http://localhost",
            "http://svc.internal",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:text/html,x",
            "http://user:secret@example.com",
            "http://example.com\\@127.0.0.1",
        ] {
            assert!(parse_url(url).is_err(), "accepted {url}");
        }
    }
    #[test]
    fn public_addresses() {
        assert!(public_ip(IpAddr::V4(Ipv4Addr::new(93, 184, 216, 34))));
        assert!(public_ip(IpAddr::V6(Ipv6Addr::new(
            0x2606, 0x4700, 0, 0, 0, 0, 0, 0x1111
        ))));
        assert!(parse_url("https://example.com/a").is_ok());
    }
}
