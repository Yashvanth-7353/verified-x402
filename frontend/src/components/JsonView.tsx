import { CopyButton } from './Copyable';

function highlight(json: string): string {
  const escaped = json
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return escaped.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(\.\d+)?([eE][+-]?\d+)?)/g,
    (match) => {
      let cls = 'jn';
      if (/^"/.test(match)) {
        cls = /:$/.test(match) ? 'jk' : 'js';
      } else if (/true|false|null/.test(match)) {
        cls = 'jb';
      }
      return `<span class="${cls}">${match}</span>`;
    },
  );
}

export function JsonView({ data, title, collapsible }: { data: unknown; title?: string; collapsible?: boolean }) {
  const json = JSON.stringify(data, null, 2);
  const body = (
    <div>
      {title && (
        <div className="copy-row" style={{ marginBottom: 8 }}>
          <span className="section-title" style={{ marginBottom: 0 }}>
            {title}
          </span>
          <CopyButton value={json} label="Copy JSON" />
        </div>
      )}
      <div className="json-block" dangerouslySetInnerHTML={{ __html: highlight(json) }} />
    </div>
  );

  if (!collapsible) return body;

  return (
    <details className="tech">
      <summary>{title ?? 'Raw JSON'}</summary>
      <div style={{ marginTop: 10 }}>{body}</div>
    </details>
  );
}
