import * as vscode from "vscode";
import * as cp from "child_process";
import * as path from "path";
import * as net from "net";
import * as fs from "fs";
import * as http from "http";

/**
 * Spawns and supervises the local FastAPI classifier server.
 * Resolves the server's working directory by walking up from the extension folder
 * to find a sibling `server/` directory.
 */
export class ServerManager {
    private proc: cp.ChildProcess | undefined;
    private url: string;

    constructor(private ctx: vscode.ExtensionContext, private out: vscode.OutputChannel) {
        const cfg = vscode.workspace.getConfiguration("moveClassifier");
        this.url = cfg.get<string>("serverUrl") ?? "http://127.0.0.1:8765";
    }

    async start(): Promise<void> {
        if (await this.ping()) {
            this.out.appendLine(`[server] already running at ${this.url}`);
            return;
        }

        const serverDir = this.resolveServerDir();
        if (!serverDir) {
            throw new Error(
                "server/ directory not found. Expected at the repo root, alongside extension/."
            );
        }

        const python = await this.resolvePython(serverDir);
        const port = this.portFromUrl(this.url);

        this.out.appendLine(`[server] launching ${python} app.py (port ${port}) in ${serverDir}`);
        this.proc = cp.spawn(python, ["app.py"], {
            cwd: serverDir,
            env: { ...process.env, PORT: String(port) },
            stdio: ["ignore", "pipe", "pipe"],
        });

        this.proc.stdout?.on("data", (b) => this.out.append(`[server] ${b}`));
        this.proc.stderr?.on("data", (b) => this.out.append(`[server] ${b}`));
        this.proc.on("exit", (code, sig) =>
            this.out.appendLine(`[server] exited code=${code} sig=${sig}`)
        );

        await this.waitForReady(60_000);
        this.out.appendLine(`[server] ready at ${this.url}`);
    }

    async stop(): Promise<void> {
        if (!this.proc) return;
        this.out.appendLine("[server] stopping");
        this.proc.kill("SIGTERM");
        await new Promise<void>((resolve) => {
            const t = setTimeout(() => {
                this.proc?.kill("SIGKILL");
                resolve();
            }, 3000);
            this.proc?.once("exit", () => {
                clearTimeout(t);
                resolve();
            });
        });
        this.proc = undefined;
    }

    private resolveServerDir(): string | undefined {
        // Walk up from the extension dir looking for a sibling `server/` directory.
        let dir = this.ctx.extensionPath;
        for (let i = 0; i < 5; i++) {
            const cand = path.join(dir, "..", "server");
            if (fs.existsSync(path.join(cand, "app.py"))) return path.resolve(cand);
            const cand2 = path.join(dir, "server");
            if (fs.existsSync(path.join(cand2, "app.py"))) return path.resolve(cand2);
            dir = path.dirname(dir);
        }
        return undefined;
    }

    private async resolvePython(serverDir: string): Promise<string> {
        const cfg = vscode.workspace.getConfiguration("moveClassifier");
        const explicit = cfg.get<string>("pythonPath") ?? "";
        if (explicit) return explicit;

        // Prefer a local venv next to server/ if present.
        const venvCandidates = [
            path.join(serverDir, ".venv", "bin", "python"),
            path.join(serverDir, "..", ".venv-1", "bin", "python"),
            path.join(serverDir, "..", ".venv", "bin", "python"),
        ];
        for (const p of venvCandidates) {
            if (fs.existsSync(p)) return p;
        }
        return process.platform === "win32" ? "python" : "python3";
    }

    private portFromUrl(u: string): number {
        try {
            const parsed = new URL(u);
            return Number(parsed.port || "8765");
        } catch {
            return 8765;
        }
    }

    private async waitForReady(timeoutMs: number): Promise<void> {
        const deadline = Date.now() + timeoutMs;
        while (Date.now() < deadline) {
            if (await this.ping()) return;
            await new Promise((r) => setTimeout(r, 500));
        }
        throw new Error(`server did not become ready within ${timeoutMs}ms`);
    }

    private ping(): Promise<boolean> {
        return new Promise((resolve) => {
            try {
                const req = http.get(this.url + "/health", { timeout: 1500 }, (res) => {
                    resolve(res.statusCode === 200);
                    res.resume();
                });
                req.on("error", () => resolve(false));
                req.on("timeout", () => {
                    req.destroy();
                    resolve(false);
                });
            } catch {
                resolve(false);
            }
        });
    }
}
