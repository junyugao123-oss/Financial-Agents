"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { MobileLanding } from "@/components/mobile-landing";

const DesktopHomeExperience = dynamic(
  () => import("@/components/home-experience").then((mod) => mod.HomeExperience),
  {
    loading: () => <HomeLoadingSurface />,
    ssr: false,
  },
);

export function HomeRouter() {
  const [isMobile, setIsMobile] = useState<boolean | null>(null);

  useEffect(() => {
    const viewportQuery = window.matchMedia("(max-width: 900px)");
    const syncViewport = () => setIsMobile(viewportQuery.matches);

    syncViewport();
    viewportQuery.addEventListener("change", syncViewport);
    return () => viewportQuery.removeEventListener("change", syncViewport);
  }, []);

  if (isMobile === false) {
    return <DesktopHomeExperience />;
  }

  return <MobileLanding />;
}

function HomeLoadingSurface() {
  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-neutral-950 px-6 text-white">
      <div className="h-2 w-32 overflow-hidden rounded-full bg-white/10">
        <div className="h-full w-1/2 animate-pulse rounded-full bg-teal-200" />
      </div>
    </main>
  );
}
