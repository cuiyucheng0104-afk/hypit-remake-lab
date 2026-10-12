import {
  createRuntimeEndpointAdapterFacet, runtimeConfigExact, runtimeConfigObject,
  runtimeConfigPositiveInteger, runtimeConfigString,
} from "@hypit/hypit/runtime-kit";
import { createAutodlMarketProvider, providerModule } from "./provider.js";

const KEYS = ["baseUrl", "tokenFile", "referenceWorkflow", "frameWorkflow", "textWorkflow", "referenceTier",
  "spendCapYuan", "ledgerFile", "pollIntervalMs", "concurrency"];

export default {
  format: "hypit.node-package@1" as const,
  hostFacets: [createRuntimeEndpointAdapterFacet({
    use: providerModule.name,
    activate(context) {
      const config = runtimeConfigObject(context.config, "AutoDL 市场");
      runtimeConfigExact(config, KEYS, "AutoDL 市场");
      const text = (key: string, fallback: string) => runtimeConfigString(config[key], `AutoDL 市场 ${key}`) ?? fallback;
      const cap = Number(config.spendCapYuan ?? 30);
      if (!Number.isFinite(cap) || cap <= 0) throw new Error("AutoDL 市场 spendCapYuan 必须是正数（元）");
      if (!context.pool) throw new Error("AutoDL 市场 Endpoint 需要 pool");
      return { endpoint: createAutodlMarketProvider({
        instance: context.instance, pool: context.pool,
        baseUrl: text("baseUrl", "https://www.autodl.art"),
        tokenFile: text("tokenFile", "~/.config/autodl/comfy_token"),
        workflows: {
          reference: text("referenceWorkflow", "minimax_h3_z0903"),
          frame: text("frameWorkflow", "minimax_h3_b99_002"),
          text: text("textWorkflow", "minimax_h3_lightx2v_no_pic"),
        },
        referenceTier: text("referenceTier", "1088p"),
        spendCapYuan: cap,
        ledgerFile: text("ledgerFile", "~/.config/autodl/market-ledger.json"),
        pollIntervalMs: runtimeConfigPositiveInteger(config.pollIntervalMs, "pollIntervalMs") ?? 8_000,
        concurrency: runtimeConfigPositiveInteger(config.concurrency, "concurrency") ?? 4,
      }).package };
    },
  })],
};
