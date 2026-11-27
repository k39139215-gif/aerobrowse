"""Run the new harness against an owned local HTTP fixture, without public dependencies."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from aerobrowse.benchmark import run
from aerobrowse.pruner import SemanticPruner

CASES = {
 'documentation':'<nav><a href="/guide">Guide</a></nav><main><h1>API reference</h1><pre>fetch(url)</pre><p>Returns a structured snapshot.</p></main>',
 'ecommerce':'<h1>Catalog</h1><article><h2>Keyboard</h2><p>₹2500</p><button>Add to basket</button><img src="/keyboard.png" alt="Mechanical keyboard"></article>',
 'news':'<article><h1>Local council approves park</h1><p>Reporter: Asha</p><p>The council voted on Monday.</p></article>',
 'dashboard':'<main><h1>Receivables</h1><dl><dt>Open</dt><dd>₹42</dd></dl><button aria-label="Refresh">↻</button></main>',
 'search':'<main><h1>Results</h1><ol><li><a href="https://example.com/one">First result</a><p>Relevant snippet</p></li></ol></main>',
 'long_article':'<article><h1>Long article</h1>'+''.join('<p>Section '+str(i)+' discusses multilingual 中文 العربية content.</p>' for i in range(100))+'</article>',
 'complex_table':'<table><caption>Balances</caption><tr><th id="name" scope="col">Name</th><th id="total">Total</th></tr><tr><td headers="name">Alpha<table><tr><td>Nested</td></tr></table></td><td headers="total">₹42</td></tr></table>',
 'form':'<form><label for="n">Name</label><input id="n"><label>Choice<select><option>A</option></select></label><label><input type="checkbox">Agree</label><button>Submit</button></form>'
}

def main():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body=('<html><head><title>Controlled documentation</title></head><body>'+CASES['documentation']+'</body></html>').encode()
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*args):
            return
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        result=run(f'http://127.0.0.1:{server.server_port}/',repeats=5,concurrency=2,allow_networks=('127.0.0.1/32',))
        Path('evidence/benchmark-local.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    finally:
        server.shutdown();server.server_close();thread.join()
    quality=[]
    for name,html in CASES.items():
        value=SemanticPruner().prune(html,'https://example.com')
        quality.append({'fixture':name, **{k:value[k] for k in ('original_tokens','extracted_tokens','token_reduction_pct','tokenizer','character_reduction_pct','quality')},
            'limitations':['Synthetic controlled markup; not representative production-site recall or framework compatibility']})
    Path('evidence/token-fixtures.json').write_text(json.dumps(quality,indent=2),encoding='utf-8')
    print('Wrote local benchmark and 8 tokenizer fixture receipts')

if __name__=='__main__':
    main()
