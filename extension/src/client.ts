import * as http from "http";
import * as https from "https";
import { URL } from "url";

export interface ClassifyResponse {
    label: string;
    confidence: number;
    top_2: { label: string; confidence: number }[];
    device: string;
}

export async function classify(serverUrl: string, code: string): Promise<ClassifyResponse> {
    const url = new URL("/classify", serverUrl);
    const body = JSON.stringify({ code });
    const lib = url.protocol === "https:" ? https : http;

    return new Promise<ClassifyResponse>((resolve, reject) => {
        const req = lib.request(
            {
                method: "POST",
                hostname: url.hostname,
                port: url.port,
                path: url.pathname,
                headers: {
                    "Content-Type": "application/json",
                    "Content-Length": Buffer.byteLength(body),
                },
                timeout: 30_000,
            },
            (res) => {
                let buf = "";
                res.setEncoding("utf8");
                res.on("data", (c) => (buf += c));
                res.on("end", () => {
                    if ((res.statusCode ?? 500) >= 400) {
                        reject(new Error(`server ${res.statusCode}: ${buf}`));
                        return;
                    }
                    try {
                        resolve(JSON.parse(buf) as ClassifyResponse);
                    } catch (e) {
                        reject(e);
                    }
                });
            }
        );
        req.on("error", reject);
        req.on("timeout", () => req.destroy(new Error("classify timeout")));
        req.write(body);
        req.end();
    });
}
