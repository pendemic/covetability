"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/discover", label: "Discover" },
  { href: "/compare", label: "Compare" },
  { href: "/covet-list", label: "Covet List" },
  { href: "/methodology", label: "Methodology" },
];

export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="topbar">
      <Link className="wordmark" href="/">
        <span aria-hidden="true" className="wordmarkDot" />
        Covetability
      </Link>
      <nav className="topnav" aria-label="Public">
        {navItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link className={active ? "topnavLink on" : "topnavLink"} href={item.href} key={item.href}>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <form className="navSearch" action="/discover" method="get" role="search">
        <input aria-label="Search a bag" name="q" placeholder="Search a bag…" type="search" />
      </form>
    </header>
  );
}
