// 版本化离线缓存保存页面资源；设备操作和健康检查仍必须访问网络。
const CACHE_NAME = "stackchan-mobile-v29";
const APP_FILES = [
  "./",
  "./index.html",
  "./styles.css?v=29",
  "./api.js",
  "./settings.js",
  "./app.js?v=29",
  "./chat.js",
  "./camera_panel.js",
  "./screen_programs.js",
  "./remote_control.js",
  "./actions_music.js",
  "./update.js",
  "./robot_3d.js?v=29",
  "./vendor/three.module.js?v=29",
  "./vendor/loaders/GLTFLoader.js?v=29",
  "./vendor/utils/BufferGeometryUtils.js?v=29",
  "./manifest.webmanifest",
  "./model-assets/stack_chan_model.glb",
  "./assets/action-robot.webp?v=6",
  "./assets/settings-robot.webp?v=6",
  "./assets/app-icon-192.png",
  "./assets/app-icon-512.png"
];

// 安装 Service Worker 时预缓存页面资源，支持后续页面资源的离线回退。
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_FILES)));
  self.skipWaiting();
});

// 激活新缓存版本并清理旧版本，减少旧脚本与新页面混用。
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.searchParams.has("pair")) {
    event.respondWith(fetch(event.request));
    return;
  }
  // 设备接口不读缓存，避免离线时用旧响应伪装实时设备状态。
  if (url.pathname.startsWith("/mobile-api/") || url.pathname === "/mobile-health") {
    event.respondWith(fetch(event.request));
    return;
  }
  if (event.request.method !== "GET") return;
  const liveResource = ["document", "style", "script"].includes(event.request.destination);
  // 文档、样式和脚本优先访问网络，网络失败时才使用已有缓存。
  if (liveResource) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
