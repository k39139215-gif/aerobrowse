"""Bounded semantic HTML extraction. Static actions are informational candidates."""
import re
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from aerobrowse.security import Limits
from aerobrowse.errors import AeroError
from aerobrowse.tokens import measure

INTERACTIVE = {'button','a','input','textarea','select','summary'}
ROLES = {'button','link','textbox','checkbox','combobox','radio','switch','menuitem'}

# Strip credentials/query/fragment from extracted destinations; query values may be tokens.
def safe_link(value: str, base: str = '') -> str:
    if not value:
        return ''
    try:
        parts = urlsplit(urljoin(base,value))
        if parts.scheme not in {'http','https'}:
            return '[unsupported destination]'
        host = parts.hostname or ''
        if ':' in host:
            host = '['+host+']'
        if parts.port:
            host += ':'+str(parts.port)
        return urlunsplit((parts.scheme,host,parts.path,'',''))
    except ValueError:
        return '[invalid destination]'

class SemanticPruner:
    UNWANTED_TAGS = {'script','style','noscript','svg','path','meta','link','template'}

    def __init__(self, *, limits: Limits | None = None, tokenizer: str = 'cl100k_base'):
        self.limits, self.tokenizer = limits or Limits(),tokenizer

    def prune(self, html: str, base_url: str = '') -> dict[str,Any]:
        if len(html.encode('utf-8')) > self.limits.response_bytes:
            raise AeroError('HTML_TOO_LARGE','HTML exceeds parser byte limit')
        soup = BeautifulSoup(html,'html.parser')
        # Iterative validation before recursive rendering bounds CPU/stack depth.
        stack: list[tuple[Any,int]] = [(soup,0)]
        count = 0
        while stack:
            node, depth = stack.pop()
            count += 1
            if count > self.limits.html_nodes or depth > self.limits.html_depth:
                raise AeroError('HTML_LIMIT_EXCEEDED','HTML node or nesting limit exceeded')
            if isinstance(node,Tag):
                stack.extend((child,depth+1) for child in node.children)
        title = soup.title.get_text(' ',strip=True) if soup.title else ('' if not html else 'Untitled Page')
        for node in list(soup.find_all(string=lambda s:isinstance(s,Comment))):
            node.extract()
        for node in list(soup.find_all(self.UNWANTED_TAGS)):
            node.decompose()
        for node in list(soup.select('[hidden], [inert], [aria-hidden="true"], input[type="hidden"]')):
            if node.parent:
                node.decompose()
        # Never expose form values, including text/textarea fields and selected tokens.
        for node in soup.find_all(['input','textarea','select']):
            if node.name == 'textarea':
                node.clear()
            node.attrs.pop('value',None)
        actions = []
        for node in soup.find_all(True):
            tag = node.name
            role = str(node.get('role',''))
            if tag not in INTERACTIVE and role not in ROLES:
                continue
            if tag == 'a' and not node.has_attr('href'):
                continue
            input_type = str(node.get('type',''))
            label = str(node.get('aria-label') or '')
            if not label and node.get('aria-labelledby'):
                label = ' '.join(soup.find(id=i).get_text(' ',strip=True) for i in str(node['aria-labelledby']).split() if soup.find(id=i))
            if not label and node.get('id'):
                labels = soup.find_all('label',attrs={'for':node['id']})
                label = ' '.join(n.get_text(' ',strip=True) for n in labels)
            text = node.get_text(' ',strip=True)
            if text.endswith(('...','…')) and node.get('title'):
                text = str(node['title'])
            label = label or text or str(node.get('placeholder') or node.get('title') or '')
            disabled = node.has_attr('disabled') or node.get('aria-disabled')=='true'
            actions.append({'id':str(len(actions)+1),'tag':tag,'element_type':tag,
                'label':label,'accessible_name':label,'role':role,'input_type':input_type,
                'value':None,'disabled':disabled,'visible':None,'executable':False,'generation':None,
                'href':safe_link(str(node.get('href','')),base_url),'name':str(node.get('name','')),
                'attributes':{'required':node.has_attr('required'),'readonly':node.has_attr('readonly')}})
        tables = []
        for table in soup.find_all('table'):
            rows = []
            for row in table.find_all('tr'):
                if row.find_parent('table') != table:
                    continue
                rows.append([{'text':cell.get_text(' ',strip=True),'header':cell.name=='th',
                    'id':cell.get('id'),'scope':cell.get('scope'),'headers':cell.get('headers',[]),
                    'rowspan':cell.get('rowspan','1'),'colspan':cell.get('colspan','1')}
                    for cell in row.find_all(['th','td'],recursive=False)])
            tables.append({'caption':table.caption.get_text(' ',strip=True) if table.caption else '', 'rows':rows})
        embedded = soup.find_all(['iframe','embed','object'])
        def render(node: Any, depth: int = 0) -> str:
            if isinstance(node,NavigableString):
                return str(node)
            if not isinstance(node,Tag):
                return ''
            tag = node.name
            if tag in {'iframe','embed','object'}:
                return '\n[Embedded content inaccessible: '+str(node.get('title') or node.get('aria-label') or tag)+' '+safe_link(str(node.get('src') or node.get('data') or ''),base_url)+']\n'
            if tag == 'img':
                return '!['+str(node.get('alt',''))+']('+safe_link(str(node.get('src','')),base_url)+')'
            if tag == 'input':
                return '[input '+str(node.get('type','text'))+' '+str(node.get('aria-label') or node.get('placeholder') or '')+(' checked' if node.has_attr('checked') else '')+']'
            text = ''.join(render(child,depth+(1 if tag in {'ul','ol'} else 0)) for child in node.children)
            if tag == 'a':
                if text.strip().endswith(('...','…')) and node.get('title'):
                    text = str(node['title'])
                return '['+text.strip()+']('+safe_link(str(node.get('href','')),base_url)+')'
            if tag in {'h1','h2','h3','h4','h5','h6'}:
                return '\n\n'+'#'*int(tag[1])+' '+text.strip()+'\n\n'
            if tag == 'li':
                return '\n'+'  '*max(0,depth-1)+'- '+text.strip()+'\n'
            if tag in {'td','th'}:
                return ' '+text.strip().replace('|','\\|')+' |'
            if tag == 'tr':
                return '\n|'+text+'\n'
            if tag == 'br':
                return '\n'
            if tag == 'pre':
                return '\n```\n'+text+'\n```\n'
            if tag in {'p','div','main','section','article','table','nav','dialog','blockquote','header','footer','ul','ol'}:
                return '\n'+text.strip()+'\n'
            return text
        markdown = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+','\n\n',render(soup)).strip()
        result = {'title':title,'markdown':markdown,'actions':actions,'tables':tables,
            'original_chars':len(html),'pruned_chars':len(markdown),
            'character_reduction_pct':round((1-len(markdown)/len(html))*100,2) if html else 0.0,
            'quality':{'node_count':count,'empty_content':not bool(markdown),
                'embedded_content_inaccessible':len(embedded),'visibility_verified':False,
                'missing_content_indicators':['embedded_content'] if embedded else []}}
        result.update(measure(html,markdown,self.tokenizer))
        return result
