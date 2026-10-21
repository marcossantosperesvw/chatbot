import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chat Jogos Online",
  description:
    "Descubra novos jogos, encontre tutoriais de instalação e tire dúvidas sobre plataformas, controles e configurações com o Chat Jogos.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
