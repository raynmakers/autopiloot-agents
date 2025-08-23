import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/auth/AuthProvider";
import { ThemeProvider } from "@/theme/ThemeProvider";

export const metadata: Metadata = {
  title: "Next.js Firebase Template",
  description: "A minimal Next.js app with Firebase integration",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <ThemeProvider>
          <AuthProvider>
            {children}
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}