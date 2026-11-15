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
                text
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
                label: label.chars().take(60).collect(),
                href,
                input_type,
            });
            action_id += 1;
        }

        // 3. Extract Clean Text & Structure
        let content_selector = Selector::parse("h1, h2, h3, h4, p, li, pre, table").unwrap();
        let mut lines = Vec::new();

        for element in document.select(&content_selector) {
            let text = element.text().collect::<String>().trim().to_string();
            if text.is_empty() {
                continue;
            }

            match element.value().name() {
                "h1" => lines.push(format!("\n# {}\n", text)),
                "h2" => lines.push(format!("\n## {}\n", text)),
                "h3" => lines.push(format!("\n### {}\n", text)),
                "h4" => lines.push(format!("\n#### {}\n", text)),
                "p" => lines.push(format!("{}\n", text)),
                "li" => lines.push(format!("* {}", text)),
                "pre" => lines.push(format!("\n```\n{}\n```\n", text)),
                _ => lines.push(text),
            }
        }

        let mut markdown = lines.join("\n");
        if markdown.len() < 40 {
            // Fallback to body text
            let body_selector = Selector::parse("body").unwrap();
            if let Some(body) = document.select(&body_selector).next() {
                markdown = body.text().collect::<Vec<_>>().join(" ");
            }
        }

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
}
