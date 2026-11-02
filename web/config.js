// Amazon Location Service 公开 API Key（浏览器端使用）。
// 权限已在 AWS 侧限制为：地图瓦片、可达圈/路线/路线优化、地点搜索；部署后再限制 Referer 域名。
window.MP_CONFIG = {
  region: "ap-northeast-1",
  apiKey: "v1.public.eyJqdGkiOiJlNjE4N2FjOC0zMjc5LTQwYjEtYWZmNS1jMGQwMmUzNTg1YTEifa49Ep6B78PQlSTwav22SYjv219ONLvGZ3zGlwso39PnE4VTz-7ViwzSXijaeXZ04CxGRiRXpxOAcoX8G9rQ67IbOW8ymdvu4gfPbRL2CpA6r5CtNRNACdgKPuSIGthFuI1HvbZouvU_cK0-qTWnHstu2oftu492Sq3nZRFqSc13ODhcBdy4AXyFawevZUTfqK7HccLrGpBJirfaQELGv8lOQa2LbdtHkq6J1lUcBo8jA4zmjLbSwvwXd68r2b99bkH9vO_zzz-cXpwjsiFvOKA6emhUcL8-RTgHk0GITkLbkTza7tJFRFHLoUzvZVd0N1dJcmsaEspTXwXEwofDPdU.YTAwN2QzYTQtMjA4OC00M2Q5LWE5ZTUtYjk4Y2U1YWUxY2Uy",
  mapStyle: "Monochrome",
  colorScheme: "Dark",
  dataVersion: "2026-11-02b", // 更新数据后修改，绕过 CDN / 浏览器缓存
};
