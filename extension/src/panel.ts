import * as vscode from "vscode";

export interface FixPanelArgs {
    code: string;
    label: string;
    confidence: number;
    uri?: string;
    range?: { start: { line: number; character: number }; end: { line: number; character: number } };
}

/**
 * Streaming fix panel. Create with `FixPanel.open()`, call `appendChunk()` as
 * tokens arrive, then `done()` when the stream completes (or `fail()` on error).
 */
export class FixPanel {
    private constructor(private readonly panel: vscode.WebviewPanel) {}

    static open(ctx: vscode.ExtensionContext, args: FixPanelArgs): FixPanel {
        const panel = vscode.window.createWebviewPanel(
            "moveClassifierFix",
            `NiceMove: ${args.label}`,
            vscode.ViewColumn.Beside,
            { enableScripts: true, retainContextWhenHidden: true }
        );
        panel.webview.html = render(args);
        ctx.subscriptions.push(panel);

        // Handle "Apply Fix" messages from the webview
        panel.webview.onDidReceiveMessage((msg) => {
            if (msg.type === "applyFix" && args.uri && args.range) {
                vscode.commands.executeCommand("move-classifier.applyFix", {
                    uri: args.uri,
                    range: args.range,
                    newText: msg.code,
                });
            }
        });

        return new FixPanel(panel);
    }

    appendChunk(text: string): void {
        this.panel.webview.postMessage({ type: "chunk", text });
    }

    done(): void {
        this.panel.webview.postMessage({ type: "done" });
    }

    fail(message: string): void {
        this.panel.webview.postMessage({ type: "error", text: message });
    }
}

function render(args: FixPanelArgs): string {
    const conf = (args.confidence * 100).toFixed(1);
    const esc = (s: string) =>
        s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

    return /* html */ `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: var(--vscode-font-family); padding: 1.2em; line-height: 1.45; }
    h2 { margin-top: 0; }
    .meta { color: var(--vscode-descriptionForeground); }
    #out {
      white-space: pre-wrap;
      font-family: var(--vscode-editor-font-family, monospace);
      font-size: var(--vscode-editor-font-size, 13px);
      margin: 1em 0;
    }
    #out pre {
      background: var(--vscode-textCodeBlock-background);
      padding: 0.8em 1em;
      border-radius: 4px;
      overflow-x: auto;
      white-space: pre;
    }
    #out strong { color: var(--vscode-textLink-foreground); }
    .cursor { display: inline-block; width: 0.5em; background: var(--vscode-editorCursor-foreground); animation: blink 1s steps(2) infinite; }
    @keyframes blink { 50% { opacity: 0; } }
    .status { color: var(--vscode-descriptionForeground); font-style: italic; margin-bottom: 0.8em; }
    .status.error { color: var(--vscode-errorForeground); font-style: normal; }
    hr { border: none; border-top: 1px solid var(--vscode-panel-border); margin: 1.5em 0; }
    #applyBtn { display: none; margin: 1em 0; padding: 0.5em 1em; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 3px; cursor: pointer; font-size: 0.9em; }
    #applyBtn:hover { background: var(--vscode-button-hoverBackground); }
  </style>
</head>
<body>
  <h2>${esc(args.label)} <span class="meta">(${conf}%)</span></h2>
  <div class="status" id="status">Streaming from Claude<span class="cursor">&nbsp;</span></div>
  <button id="applyBtn">&#9998; Apply Fix</button>
  <div id="out"></div>
  <hr>
  <details>
    <summary>Original snippet</summary>
    <pre><code>${esc(args.code)}</code></pre>
  </details>
  <script>
    const vscode = acquireVsCodeApi();
    const out = document.getElementById("out");
    const status = document.getElementById("status");
    const applyBtn = document.getElementById("applyBtn");
    let buffer = "";

    function escapeHtml(s) {
      return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function extractCodeBlock() {
      // Extract the last code block from the response
      const matches = buffer.match(/\`\`\`(?:move|diff|rust)?\\n?([\\s\\S]*?)\`\`\`/g);
      if (!matches) return null;
      const last = matches[matches.length - 1];
      return last.replace(/\`\`\`(?:move|diff|rust)?\\n?/, "").replace(/\`\`\`$/, "").trim();
    }

    function rerender() {
      const md = escapeHtml(buffer)
        .replace(/\`\`\`(?:move|diff|rust)?\\n?([\\s\\S]*?)\`\`\`/g, "<pre><code>$1</code></pre>")
        .replace(/\\*\\*(.+?)\\*\\*/g, "<strong>$1</strong>");
      out.innerHTML = md;
    }

    applyBtn.addEventListener("click", () => {
      const code = extractCodeBlock();
      if (code) {
        vscode.postMessage({ type: "applyFix", code });
        applyBtn.textContent = "Applied!";
        applyBtn.disabled = true;
      }
    });

    window.addEventListener("message", (e) => {
      const m = e.data;
      if (m.type === "chunk") {
        buffer += m.text;
        rerender();
      } else if (m.type === "done") {
        status.textContent = "Done.";
        if (extractCodeBlock()) {
          applyBtn.style.display = "inline-block";
        }
      } else if (m.type === "error") {
        status.textContent = "Error: " + m.text;
        status.classList.add("error");
      }
    });
  </script>
</body>
</html>`;
}
