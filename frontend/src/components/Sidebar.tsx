"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { FilePlus2, LayoutDashboard, Leaf } from "lucide-react";
import { API_URL } from "@/lib/api";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/new", label: "New investigation", icon: FilePlus2 },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    const ping = () =>
      fetch(`${API_URL}/health`, { cache: "no-store" })
        .then((r) => alive && setOnline(r.ok))
        .catch(() => alive && setOnline(false));
    ping();
    const timer = setInterval(ping, 15000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" || pathname.startsWith("/investigations") : pathname.startsWith(href);

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <Leaf size={22} />
        </div>
        <div>
          <div className="brand-name">SENTRIX AI</div>
          <div className="brand-tag">Beyond Claims. Into Evidence.</div>
        </div>
      </div>
      <nav className="nav">
        {NAV.map((item) => {
          const Icon = item.icon;
          return (
            <Link key={item.href} href={item.href} className={`nav-item ${isActive(item.href) ? "active" : ""}`}>
              <Icon size={18} />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="side-foot">
        <strong>
          <span className={`status-dot ${online === true ? "on" : online === false ? "off" : ""}`} />
          System status
        </strong>
        {online === null ? "Checking..." : online ? "API connected" : "API offline: start the backend"}
        <div style={{ marginTop: 8 }}>Decision support for human review. Not an approval, certification or finding of fraud.</div>
      </div>
    </aside>
  );
}