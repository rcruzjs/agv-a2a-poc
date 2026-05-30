from html.parser import HTMLParser

class StackInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag in ('img', 'br', 'hr', 'input', 'meta', 'link', 'col', 'base', 'area', 'param', 'source', 'track', 'wbr'):
            return
        attrs_dict = dict(attrs)
        self.stack.append((tag, attrs_dict, self.getpos()))

    def handle_endtag(self, tag):
        if tag in ('img', 'br', 'hr', 'input', 'meta', 'link', 'col', 'base', 'area', 'param', 'source', 'track', 'wbr'):
            return
        if self.stack:
            last_tag, last_attrs, pos = self.stack[-1]
            if last_tag == tag:
                self.stack.pop()
            else:
                print(f"Error: Trying to close <{tag}> but active tag is <{last_tag}> (opened at line {pos[0]})")
                self.stack.pop()

with open('static/index.html', encoding='utf-8') as f:
    html = f.read()

checker = StackInspector()
checker.feed(html)

print("Remaining stack at end of file:")
for idx, (t, a, pos) in enumerate(checker.stack):
    id_str = f" id='{a.get('id')}'" if 'id' in a else ''
    class_str = f" class='{a.get('class')}'" if 'class' in a else ''
    print(f"  {idx:2d}: <{t}{id_str}{class_str}> opened at line {pos[0]}")
