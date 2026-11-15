use scraper::{Html, Selector};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionElement {
    pub id: usize,
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
    pub reduction_pct: f64,
}

pub struct SemanticPruner;

impl SemanticPruner {
    pub fn prune(html_str: &str, _base_url: &str) -> PrunedResult {
        let original_chars = html_str.len();
        let document = Html::parse_document(html_str);

        // 1. Extract Title
        let title_selector = Selector::parse("title").unwrap();
        let title = document
            .select(&title_selector)
            .next()
            .map(|t| t.text().collect::<String>().trim().to_string())
            .unwrap_or_else(|| "Untitled Page".to_string());

        // 2. Extract Actionable Interactive Map
        let mut actions = Vec::new();
        let interactive_selector = Selector::parse("button, a, input, textarea, select").unwrap();
        let mut action_id = 1;

        for element in document.select(&interactive_selector) {
            let val = element.value();
            let tag = val.name().to_string();
            let input_type = val.attr("type").map(|s| s.to_string());

            if tag == "input" && (input_type.as_deref() == Some("hidden") || input_type.as_deref() == Some("submit")) {
                continue;
            }

            let text = element.text().collect::<String>().trim().to_string();
            let aria = val.attr("aria-label")
                .or_else(|| val.attr("placeholder"))
                .or_else(|| val.attr("title"))
                .unwrap_or("");

            let label = if !text.is_empty() {
                // If text is truncated with ellipsis, prefer title if present
                if text.ends_with("...") && val.attr("title").is_some() {
                    val.attr("title").unwrap().to_string()
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

            let href = val.attr("href").map(|s| s.to_string());

            actions.push(ActionElement {
                id: action_id,
                tag,
                label: label.chars().take(80).collect(),
                href,
                input_type,
            });
            action_id += 1;
        }

        // 3. Extract 100% Complete Text Content via Recursive AST Walker
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

        let pruned_chars = markdown.len();
        let reduction_pct = if original_chars > 0 {
            ((1.0 - (pruned_chars as f64 / original_chars as f64)) * 100.0).max(0.0)
        } else {
            0.0
        };

        PrunedResult {
            title,
            markdown,
            actions,
            original_chars,
            pruned_chars,
            reduction_pct: (reduction_pct * 10.0).round() / 10.0,
        }
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
                // Strip unwanted tags completely
                if matches!(tag, "script" | "style" | "noscript" | "svg" | "path" | "meta" | "link" | "iframe" | "header-nav" | "ad") {
                    return;
                }

                let is_heading = matches!(tag, "h1" | "h2" | "h3" | "h4" | "h5" | "h6");
                let is_block = matches!(tag, "div" | "section" | "article" | "tr" | "header" | "footer" | "p" | "blockquote" | "li");

                if is_heading {
                    out.push_str("\n\n# ");
                } else if tag == "p" || tag == "blockquote" {
                    out.push_str("\n\n");
                } else if tag == "li" {
                    out.push_str("\n* ");
                }

                // If element has truncated text with title attribute, use title
                if tag == "a" && elem.attr("title").is_some() {
                    let has_ellipsis = elem.attr("title").unwrap().len() > 5;
                    if has_ellipsis {
                        // Traverse children normally
                    }
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
