self.addEventListener("push", (event) => {
  const data = event.data?.json() || { title: "Simple Blog", body: "Новое сообщение" };
  event.waitUntil(self.registration.showNotification(data.title, { body: data.body, icon: "/simple-mark.svg", data: { url: "/messages" } }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data?.url || "/messages"));
});
