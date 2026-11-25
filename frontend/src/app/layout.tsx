import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "智能采购助手 - ERP Agent",
  description: "基于 Harness Engineering 架构的智能采购助手",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // 浏览器扩展（例如沉浸式翻译）可能在水合前给 <html> 添加属性；
    // 水合是为服务端页面绑定客户端交互。仅忽略根元素的属性不匹配，
    // 下方应用内容的水合检查仍保持启用。
    <html lang="zh-CN" className="h-full antialiased" suppressHydrationWarning>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
