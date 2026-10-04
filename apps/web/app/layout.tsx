import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ConfirmProvider } from "@/components/ui/ConfirmProvider";
import { ToastProvider } from "@/components/ui/Toast";
import { MotionProvider } from "@/lib/theme/MotionProvider";
import { ThemeProvider } from "@/lib/theme/ThemeProvider";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: { default: "CyntraAI", template: "%s | CyntraAI" },
  description: "An AI platform for chat, mock interviews, and resume ATS scoring.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <MotionProvider>
            <ToastProvider>
              <ConfirmProvider>{children}</ConfirmProvider>
            </ToastProvider>
          </MotionProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
