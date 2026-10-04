import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PDTT | Patient Therapy Assessment",
  description: "Patient intake, four-organ evidence assessment, anatomical timeline, and downloadable reports.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
