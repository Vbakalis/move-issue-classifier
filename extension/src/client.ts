/**
 * Shared response shape for classification results. Historically produced by
 * an HTTP call to a local FastAPI server; classification now runs in-process
 * (see localClassifier.ts), but the shape is kept as the common contract.
 */
export interface ClassifyResponse {
    label: string;
    confidence: number;
    top_2: { label: string; confidence: number }[];
    device: string;
}
