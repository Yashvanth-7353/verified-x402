export async function onRequest(context) {
  const url = new URL(context.request.url);
  const targetUrl = `https://verified-x402-backend.onrender.com${url.pathname}${url.search}`;
  
  const modifiedRequest = new Request(targetUrl, {
    method: context.request.method,
    headers: context.request.headers,
    body: context.request.body,
    redirect: "manual"
  });

  return fetch(modifiedRequest);
}
