import Script from "next/script";
import { HomeExperience } from "@/components/home-experience";

export default function Home() {
  return (
    <>
      <Script id="home-entry-scroll-guard" strategy="beforeInteractive">
        {`
          (function () {
            try {
              if ("scrollRestoration" in window.history) {
                window.history.scrollRestoration = "manual";
              }
              if (window.location.pathname === "/" && window.location.hash && window.location.hash !== "#start") {
                window.history.replaceState(null, "", window.location.pathname + window.location.search + "#start");
              }
            } catch (error) {}
          })();
        `}
      </Script>
      <HomeExperience />
    </>
  );
}
