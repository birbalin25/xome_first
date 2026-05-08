import Header from "./components/layout/Header";
import AppShell from "./components/layout/AppShell";

export default function App() {
  return (
    <div className="flex h-screen flex-col">
      <Header />
      <AppShell />
    </div>
  );
}
