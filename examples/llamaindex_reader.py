"""
AeroBrowse + LlamaIndex Reader Example
=======================================
High-efficiency web reader for RAG pipelines and vector stores.
"""

from typing import List
from llama_index.core.readers.base import BaseReader
from llama_index.core.schema import Document
from aerobrowse import AeroBrowser


class AeroBrowseWebReader(BaseReader):
    """LlamaIndex reader powered by AeroBrowse token optimization."""

    def __init__(self):
        super().__init__()
        self.browser = AeroBrowser()

    def load_data(self, urls: List[str]) -> List[Document]:
        docs = []
        for url in urls:
            res = self.browser.fetch(url)
            doc = Document(
                text=res["markdown"],
                metadata={
                    "title": res["title"],
                    "url": res["url"],
                    "reduction_pct": res["reduction_pct"],
                    "engine": res["engine"]
                }
            )
            docs.append(doc)
        return docs


if __name__ == "__main__":
    reader = AeroBrowseWebReader()
    docs = reader.load_data(["https://news.ycombinator.com"])
    print(f"Loaded {len(docs)} documents into LlamaIndex format.")
    print("Document Title:", docs[0].metadata["title"])
