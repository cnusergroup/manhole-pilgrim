// apiKey: Amazon Location browser key for MAP TILES ONLY (geo-maps:GetTile), referer-restricted, expires 2026-12-31.
//         It is public by design (every visitor's browser receives it) and cannot call Places or Routes.
// proxyUrl: API Gateway + Lambda (infra/proxy.yaml) for place search, isolines and routing. The proxy holds the
//         IAM permissions, validates input, rate-limits, and enforces a hard daily cap per operation.
// Deploying your own copy? Replace both values; see README "Deploy your own copy".
window.MP_CONFIG = {
  region: "ap-northeast-1",
  apiKey: "v1.public.eyJqdGkiOiJjNWI3NWJhMC04Y2VmLTQwMGEtYmQ0Mi02OTkyYTE2N2Y5ZDAifZH4K1BNFkVKfIEpX0140aN081NGuIKE0dWJDxbBZSM6PCrz6QHjvUN6k4O-yKGAYm7m54GpK315mXox3OT35VFEs7RVmdGxhiHM-UdfL7A_48r54m3TBA-Y0U1QqUWo6i_4jg153OyU_OtP1l1xWmQ4GZn27DMMGEWt8b_mcpHvvuptCJk1BeETXg88XHl_2I8uEjAEEkKd_p3FFho2GN_owku9cTRQMRdVgF20t_T9WxaLdWJIHYX0CyfKRHBVAy9ruwvjLdg4Gt-miUV-s7QB2uxe6_Tod5OWaOzHqkY0GHKUu_P_8gUHZ1DeG2Y6bEycnIbszLe2nBFSFWdaITc.YTAwN2QzYTQtMjA4OC00M2Q5LWE5ZTUtYjk4Y2U1YWUxY2Uy",
  proxyUrl: "https://lbhaxekem4.execute-api.ap-northeast-1.amazonaws.com",
  mapStyle: "Monochrome",
  colorScheme: "Dark",
  dataVersion: "2026-11-02c", // bump after regenerating data to bypass CDN / browser caches
};
