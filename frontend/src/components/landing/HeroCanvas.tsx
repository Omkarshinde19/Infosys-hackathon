"use client";

import dynamic from "next/dynamic";

// WebGL only exists in the browser.
export const HeroCanvas = dynamic(() => import("./HeroScene"), { ssr: false });
