import Anthropic from "@anthropic-ai/sdk";

export interface AskClaudeArgs {
    apiKey: string;
    model: string;
    code: string;
    label: string;       // one of the 5 labels, or "uncertain"
    confidence: number;  // 0..1
}

const SYSTEM_PROMPT = `You are an expert reviewer of Move smart-contract code on the Sui blockchain.
A small local classifier has already triaged the snippet you are shown into one of five categories:
Perfect, SecurityError, SemanticError, StyleError, SyntaxError, or "uncertain".
Your job is to (a) confirm or correct the diagnosis in one short sentence, and
(b) suggest a concrete fix as a unified diff or a corrected snippet.
Be terse. Move-aware. Do not invent APIs that are not in standard Sui Move.`;

function userPrompt(args: AskClaudeArgs): string {
    const conf = (args.confidence * 100).toFixed(1);
    const labelLine =
        args.label === "uncertain"
            ? `The classifier is uncertain (top label confidence ${conf}%). Diagnose from scratch.`
            : `The classifier predicts: ${args.label} (confidence ${conf}%).`;
    return `${labelLine}

Snippet (Move):

\`\`\`move
${args.code}
\`\`\`

Respond in two short sections:

**Diagnosis** — one sentence.
**Fix** — corrected snippet or unified diff. Keep it minimal.`;
}

export async function askClaude(args: AskClaudeArgs): Promise<string> {
    const client = new Anthropic({ apiKey: args.apiKey });
    const msg = await client.messages.create({
        model: args.model,
        max_tokens: 1024,
        system: SYSTEM_PROMPT,
        messages: [{ role: "user", content: userPrompt(args) }],
    });
    const parts = msg.content
        .filter((b) => b.type === "text")
        .map((b) => (b as { type: "text"; text: string }).text);
    return parts.join("\n").trim();
}

/**
 * Stream Claude's response, calling `onText` for each text chunk.
 * Resolves when the stream completes; rejects on stream error.
 */
export async function askClaudeStream(
    args: AskClaudeArgs,
    onText: (chunk: string) => void
): Promise<void> {
    const client = new Anthropic({ apiKey: args.apiKey });
    const stream = client.messages.stream({
        model: args.model,
        max_tokens: 1024,
        system: SYSTEM_PROMPT,
        messages: [{ role: "user", content: userPrompt(args) }],
    });
    stream.on("text", (chunk: string) => onText(chunk));
    await stream.finalMessage();
}
