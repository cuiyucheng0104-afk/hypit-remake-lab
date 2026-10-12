import {
  createRuntimeEndpointAdapterFacet, runtimeConfigExact, runtimeConfigObject,
  runtimeConfigPositiveInteger, runtimeConfigString,
} from "@hypit/hypit/runtime-kit";
import { createComfyH3Provider, providerModule } from "./provider.js";

export default {
  format: "hypit.node-package@1" as const,
  hostFacets: [createRuntimeEndpointAdapterFacet({
    use: providerModule.name,
    activate(context) {
      const config = runtimeConfigObject(context.config, "ComfyUI H3");
      runtimeConfigExact(config, ["baseUrl", "pollIntervalMs"], "ComfyUI H3");
      const baseUrl = runtimeConfigString(config.baseUrl, "ComfyUI H3 baseUrl");
      if (!baseUrl || !context.pool) throw new Error("ComfyUI H3 requires baseUrl and pool");
      return { endpoint: createComfyH3Provider({
        instance: context.instance, pool: context.pool, baseUrl,
        pollIntervalMs: runtimeConfigPositiveInteger(config.pollIntervalMs, "pollIntervalMs") ?? 5_000,
      }) };
    },
  })],
};
