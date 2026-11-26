use scraper::{Html, Selector};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionElement {
    pub id: usize,
    pub executable: bool,
    pub tag: String,
    pub label: String,
    pub href: Option<String>,
    pub input_type: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrunedResult {
    pub title: String,
    pub markdown: String,
    pub actions: Vec<ActionElement>,
    pub original_chars: usize,
    pub pruned_chars: usize,
    pub character_reduction_pct: f64,
    pub original_tokens: Option<usize>,
    pub extracted_tokens: Option<usize>,
    pub token_reduction_pct: Option<f64>,
    pub tokenizer: Option<String>,
    pub limitations: Vec<String>,
}

pub struct SemanticPruner;

impl SemanticPruner {
    pub fn prune(html_str: &str, _base_url: &str) -> Result<PrunedResult, String> {
        if html_str.len() > crate::security::MAX_BYTES {
            return Err("HTML_TOO_LARGE".into());
        }
        let original_chars = html_str.chars().count();
        let document = Html::parse_document(html_str);
        Self::validate_tree(&document)?;

        // 1. Extract Title
        let title_selector = Selector::parse("title").map_err(|_| "PARSER_ERROR")?;
        let title = document
            .select(&title_selector)
            .next()
            .map(|t| t.text().collect::<String>().trim().to_string())
            .unwrap_or_else(|| "Untitled Page".to_string());

        // Build label indexes once; never scan the full document for each control.
        let mut ids = std::collections::HashMap::new();
        let mut labels: std::collections::HashMap<String, Vec<String>> =
            std::collections::HashMap::new();
        for element in document.tree.nodes().filter_map(scraper::ElementRef::wrap) {
            if let Some(id) = element.value().attr("id") {
                ids.entry(id.to_string()).or_insert(element);
            }
            if element.value().name() == "label" {
                if let Some(target) = element.value().attr("for") {
                    labels
                        .entry(target.to_string())
                        .or_default()
                        .push(Self::label_text(element));
                }
            }
        }
        // Static candidates are informational; never resolve them into live ordinals.
        let mut actions = Vec::new();
        let selector = Selector::parse("a[href],button,input,textarea,select,summary,[role=button],[role=link],[role=textbox],[role=checkbox],[role=combobox],[role=radio],[role=switch],[role=menuitem]")
            .map_err(|_| "PARSER_ERROR")?;
        for element in document.select(&selector) {
            if !Self::included(element) {
                continue;
            }
            let val = element.value();
            let tag = val.name().to_string();
            let input_type = val.attr("type").map(str::to_string);
            let href = val
                .attr("href")
                .and_then(|raw| Self::safe_href(raw, _base_url));
            let label = Self::accessible_name(element, &ids, &labels);
            actions.push(ActionElement {
                id: actions.len() + 1,
                executable: false,
                tag,
                label,
                href,
                input_type,
            });
        }

        // 3. Extract bounded semantic text
        let mut raw_markdown = String::new();
        Self::walk_tree(document.tree.root(), &mut raw_markdown);

        // Normalize whitespace and multiple newlines
        let mut cleaned_lines = Vec::new();
        for line in raw_markdown.lines() {
            let trimmed = line.trim();
            if !trimmed.is_empty() {
                cleaned_lines.push(trimmed);
            }
        }
        let markdown = cleaned_lines.join("\n\n");

        let pruned_chars = markdown.chars().count();
        static TOKENIZER: std::sync::OnceLock<Result<tiktoken_rs::CoreBPE, String>> =
            std::sync::OnceLock::new();
        let enc = TOKENIZER
            .get_or_init(|| tiktoken_rs::cl100k_base().map_err(|_| "TOKENIZER_ERROR".into()))
            .as_ref()
            .map_err(Clone::clone)?;
        let original_tokens = enc.encode_ordinary(html_str).len();
        let extracted_tokens = enc.encode_ordinary(&markdown).len();
        let token_reduction = if original_tokens > 0 {
            (1.0 - extracted_tokens as f64 / original_tokens as f64) * 100.0
        } else {
            0.0
        };
        let reduction_pct = if original_chars > 0 {
            ((1.0 - (pruned_chars as f64 / original_chars as f64)) * 100.0).max(0.0)
        } else {
            0.0
        };

        Ok(PrunedResult {
            title,
            markdown,
            actions,
            original_chars,
            pruned_chars,
            character_reduction_pct: (reduction_pct * 10.0).round() / 10.0,
            original_tokens: Some(original_tokens), extracted_tokens: Some(extracted_tokens), token_reduction_pct: Some(token_reduction), tokenizer: Some("tiktoken-rs/0.12.1:cl100k_base".into()),
            limitations: vec!["Native static extraction does not provide executable action IDs or verified CSS visibility".into()],
        })
    }

    fn included(element: scraper::ElementRef<'_>) -> bool {
        for node in std::iter::once(element)
            .chain(element.ancestors().filter_map(scraper::ElementRef::wrap))
        {
            let value = node.value();
            if value.attr("hidden").is_some()
                || value.attr("inert").is_some()
                || value.attr("aria-hidden") == Some("true")
                || matches!(value.name(), "script" | "style" | "noscript" | "template")
                || (value.name() == "input"
                    && value
                        .attr("type")
                        .is_some_and(|v| v.eq_ignore_ascii_case("hidden")))
            {
                return false;
            }
        }
        true
    }

    fn safe_href(raw: &str, base: &str) -> Option<String> {
        let mut url = url::Url::options()
            .base_url(url::Url::parse(base).ok().as_ref())
            .parse(raw)
            .ok()?;
        if !matches!(url.scheme(), "http" | "https") {
            return None;
        }
        url.set_username("").ok()?;
        url.set_password(None).ok()?;
        url.set_query(None);
        url.set_fragment(None);
        Some(url.to_string())
    }

    fn label_text(element: scraper::ElementRef<'_>) -> String {
        let mut parts = Vec::new();
        for node in element.descendants() {
            if let scraper::node::Node::Text(text) = node.value() {
                let in_control = node
                    .ancestors()
                    .filter_map(scraper::ElementRef::wrap)
                    .take_while(|parent| parent.id() != element.id())
                    .any(|parent| matches!(parent.value().name(), "input" | "textarea" | "select"));
                if !in_control && !text.trim().is_empty() {
                    parts.push(text.trim().to_string());
                }
            }
        }
        parts.join(" ")
    }

    fn accessible_name(
        element: scraper::ElementRef<'_>,
        ids: &std::collections::HashMap<String, scraper::ElementRef<'_>>,
        labels: &std::collections::HashMap<String, Vec<String>>,
    ) -> String {
        let val = element.value();
        if let Some(label) = val.attr("aria-label").filter(|s| !s.trim().is_empty()) {
            return label.trim().to_string();
        }
        if let Some(ids_attr) = val.attr("aria-labelledby") {
            let labels = ids_attr
                .split_whitespace()
                .filter_map(|id| ids.get(id))
                .map(|node| Self::label_text(*node))
                .collect::<Vec<_>>()
                .join(" ");
            if !labels.is_empty() {
                return labels;
            }
        }
        if let Some(id) = val.attr("id") {
            if let Some(label) = labels.get(id) {
                let label = label.join(" ");
                if !label.is_empty() {
                    return label;
                }
            }
        }
        if let Some(label) = element
            .ancestors()
            .filter_map(scraper::ElementRef::wrap)
            .find(|node| node.value().name() == "label")
        {
            let text = Self::label_text(label);
            if !text.is_empty() {
                return text;
            }
        }
        let text = if matches!(val.name(), "input" | "textarea" | "select") {
            String::new()
        } else {
            Self::label_text(element)
        };
        if !text.is_empty() {
            return text;
        }
        let images = element
            .descendants()
            .filter_map(scraper::ElementRef::wrap)
            .filter(|node| node.value().name() == "img")
            .filter_map(|node| node.value().attr("alt"))
            .collect::<Vec<_>>()
            .join(" ");
        if !images.is_empty() {
            return images;
        }
        val.attr("alt")
            .or_else(|| val.attr("placeholder"))
            .or_else(|| val.attr("title"))
            .unwrap_or("")
            .to_string()
    }

    fn validate_tree(document: &Html) -> Result<(), String> {
        let mut stack = vec![(document.tree.root(), 0usize)];
        let mut nodes = 0;
        while let Some((node, depth)) = stack.pop() {
            nodes += 1;
            if nodes > 100_000 || depth > 128 {
                return Err("HTML_LIMIT_EXCEEDED".into());
            }
            stack.extend(node.children().map(|n| (n, depth + 1)));
        }

        Ok(())
    }

    fn walk_tree(node: ego_tree::NodeRef<scraper::node::Node>, out: &mut String) {
        match node.value() {
            scraper::node::Node::Text(text) => {
                let trimmed = text.trim();
                if !trimmed.is_empty() {
                    out.push_str(trimmed);
                    out.push(' ');
                }
            }
            scraper::node::Node::Element(elem) => {
                let tag = elem.name();
                if elem.attr("hidden").is_some()
                    || elem.attr("inert").is_some()
                    || elem.attr("aria-hidden") == Some("true")
                    || (tag == "input" && elem.attr("type") == Some("hidden"))
                {
                    return;
                }
                if tag == "textarea" {
                    out.push_str("[textarea: value omitted]");
                    return;
                }
                if matches!(tag, "iframe" | "embed" | "object") {
                    out.push_str("\n[Embedded content inaccessible: ");
                    out.push_str(elem.attr("title").unwrap_or(tag));
                    out.push_str("]\n");
                    return;
                }
                // Strip unwanted tags completely
                if matches!(
                    tag,
                    "script"
                        | "style"
                        | "noscript"
                        | "template"
                        | "svg"
                        | "path"
                        | "meta"
                        | "link"
                        | "header-nav"
                        | "ad"
                ) {
                    return;
                }

                let is_heading = matches!(tag, "h1" | "h2" | "h3" | "h4" | "h5" | "h6");
                let is_block = matches!(
                    tag,
                    "div"
                        | "section"
                        | "article"
                        | "tr"
                        | "header"
                        | "footer"
                        | "p"
                        | "blockquote"
                        | "li"
                );

                if is_heading {
                    out.push_str("\n\n# ");
                } else if tag == "p" || tag == "blockquote" {
                    out.push_str("\n\n");
                } else if tag == "li" {
                    out.push_str("\n* ");
                }

                for child in node.children() {
                    Self::walk_tree(child, out);
                }

                if is_heading || tag == "p" || tag == "blockquote" {
                    out.push_str("\n\n");
                } else if is_block && !out.ends_with('\n') {
                    out.push('\n');
                }
            }
            _ => {
                for child in node.children() {
                    Self::walk_tree(child, out);
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn measures_real_tokens_and_rejects_deep_documents() {
        let html = "<h1>Hello 世界</h1>";
        let result = SemanticPruner::prune(html, "").expect("fixture should parse");
        let enc = tiktoken_rs::cl100k_base().expect("tokenizer should initialize");
        assert_eq!(
            result.original_tokens,
            Some(enc.encode_ordinary(html).len())
        );
        assert_eq!(result.original_chars, html.chars().count());
        assert!(result.tokenizer.is_some());
        assert!(
            SemanticPruner::prune(&("<div>".repeat(200) + "x" + &"</div>".repeat(200)), "")
                .is_err()
        );
    }
    #[test]
    fn does_not_expose_form_values_as_actions() {
        let result=SemanticPruner::prune("<textarea>SECRET</textarea><input type=hidden value=TOKEN><iframe title=Report></iframe>","").expect("fixture parses");
        assert!(!result.markdown.contains("SECRET"));
        assert!(result.markdown.contains("Report"));
        assert!(result
            .actions
            .iter()
            .all(|a| !a.executable && !a.label.contains("SECRET")));
    }
    #[test]
    fn hidden_ancestors_and_credential_urls_do_not_leak_into_actions() {
        let result = SemanticPruner::prune(
            r#"<div hidden><button>HIDDEN_SECRET</button></div><template><button>TEMPLATE_SECRET</button></template><a href="https://user:SECRET@example.com/page?token=SECRET"> </a><a href="/next?q=TOKEN">Next</a><input type=submit value=SECRET>"#,
            "https://example.com/base",
        ).expect("fixture parses");
        let output = serde_json::to_string(&result).expect("serialize");
        assert!(!output.contains("SECRET"));
        assert_eq!(result.actions.len(), 3);
        assert_eq!(
            result.actions[0].href.as_deref(),
            Some("https://example.com/page")
        );
        assert_eq!(
            result.actions[1].href.as_deref(),
            Some("https://example.com/next")
        );
    }

    #[test]
    fn accessible_name_priority_and_image_text_match_static_contract() {
        let result = SemanticPruner::prune(
            r#"<label for="n">Full name</label><input id="n"><button aria-label="Accessible">Visual</button><a href="/photo"><img alt="Photo detail"></a>"#,
            "https://example.com",
        ).expect("fixture parses");
        assert_eq!(result.actions[0].label, "Full name");
        assert_eq!(result.actions[1].label, "Accessible");
        assert_eq!(result.actions[2].label, "Photo detail");
    }
}
