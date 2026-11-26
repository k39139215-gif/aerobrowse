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

        // 2. Extract Actionable Interactive Map
        let mut actions = Vec::new();
        let interactive_selector =
            Selector::parse("button, a, input, textarea, select").map_err(|_| "PARSER_ERROR")?;
        let mut action_id = 1;

        for element in document.select(&interactive_selector) {
            let val = element.value();
            let tag = val.name().to_string();
            let input_type = val.attr("type").map(|s| s.to_string());

            if tag == "input"
                && (input_type.as_deref() == Some("hidden")
                    || input_type.as_deref() == Some("submit"))
            {
                continue;
            }

            if val.attr("hidden").is_some()
                || val.attr("aria-hidden") == Some("true")
                || val.attr("inert").is_some()
            {
                continue;
            }
            let text = if matches!(tag.as_str(), "textarea" | "select") {
                String::new()
            } else {
                element.text().collect::<String>().trim().to_string()
            };
            let aria = val
                .attr("aria-label")
                .or_else(|| val.attr("placeholder"))
                .or_else(|| val.attr("title"))
                .unwrap_or("");

            let label = if !text.is_empty() {
                // If text is truncated with ellipsis, prefer title if present
                if text.ends_with("...") && val.attr("title").is_some() {
                    val.attr("title").unwrap_or("").to_string()
                } else {
                    text
                }
            } else if !aria.is_empty() {
                aria.to_string()
            } else if let Some(href) = val.attr("href") {
                href.to_string()
            } else {
                format!("<{}>", tag)
            };

            let href = val
                .attr("href")
                .and_then(|s| url::Url::parse(s).ok())
                .filter(|u| matches!(u.scheme(), "http" | "https"))
                .map(|mut u| {
                    u.set_query(None);
                    u.set_fragment(None);
                    let _ = u.set_username("");
                    let _ = u.set_password(None);
                    u.to_string()
                });

            actions.push(ActionElement {
                id: action_id,
                executable: false,
                tag,
                label: label.chars().take(80).collect(),
                href,
                input_type,
            });
            action_id += 1;
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
}
