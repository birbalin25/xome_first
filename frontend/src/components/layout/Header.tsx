import { Home } from "lucide-react";

export default function Header() {
  return (
    <header className="bg-xome-900 text-white shadow-lg">
      <div className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-3">
          <Home className="h-7 w-7 text-xome-400" />
          <div>
            <h1 className="text-xl font-bold tracking-tight">
              Xome Campaign Platform
            </h1>
            <p className="text-xs text-xome-300">
              Personalized email campaigns for high-intent buyers
            </p>
          </div>
        </div>
      </div>
    </header>
  );
}
