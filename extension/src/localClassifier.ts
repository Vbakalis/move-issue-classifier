import * as path from "path";
import { ClassifyResponse } from "./client";

const LABELS = ["Perfect", "SecurityError", "SemanticError", "StyleError", "SyntaxError"];

interface LoadedModel {
    tokenizer: any;
    model: any;
}

let modelPromise: Promise<LoadedModel> | undefined;

async function getModel(extensionPath: string): Promise<LoadedModel> {
    if (!modelPromise) {
        modelPromise = (async () => {
            const { AutoTokenizer, AutoModelForSequenceClassification, env } = await import(
                "@huggingface/transformers"
            );
            env.allowLocalModels = true;
            env.allowRemoteModels = false;
            const modelPath = path.join(extensionPath, "model");
            const tokenizer = await AutoTokenizer.from_pretrained(modelPath, { local_files_only: true });
            const model = await AutoModelForSequenceClassification.from_pretrained(modelPath, {
                dtype: "q8",
                local_files_only: true,
            } as any);
            return { tokenizer, model };
        })();
        // Don't cache a rejected load — let the next call retry from scratch.
        modelPromise.catch(() => {
            modelPromise = undefined;
        });
    }
    return modelPromise;
}

/** Forces the next classification to reload the model from disk. */
export function reloadLocalModel(): void {
    modelPromise = undefined;
}

function softmax(logits: number[]): number[] {
    const max = Math.max(...logits);
    const exps = logits.map((x) => Math.exp(x - max));
    const sum = exps.reduce((a, b) => a + b, 0);
    return exps.map((x) => x / sum);
}

/**
 * In-process replacement for client.ts's classify() — same ClassifyResponse
 * shape, no HTTP call, no local server. Runs the quantized ONNX export of the
 * CodeBERT+LoRA model directly inside the extension host via transformers.js.
 * Tokenizes with truncation matching the original server (max_length=512) so
 * whole-file diagnosis and workspace scans don't choke on long files.
 */
export async function classifyLocal(extensionPath: string, code: string): Promise<ClassifyResponse> {
    const { tokenizer, model } = await getModel(extensionPath);

    const inputs = await tokenizer(code, { truncation: true, max_length: 512 });
    const output = await model(inputs);
    const logits: number[] = Array.from(output.logits.data as ArrayLike<number>);
    const probs = softmax(logits);

    const pairs = LABELS.map((label, i) => ({ label, confidence: probs[i] })).sort(
        (a, b) => b.confidence - a.confidence
    );

    return {
        label: pairs[0].label,
        confidence: pairs[0].confidence,
        top_2: pairs.slice(0, 2),
        device: "cpu (onnxruntime-node, in-process)",
    };
}
