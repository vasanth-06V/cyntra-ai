"use client";

import { Canvas } from "@react-three/fiber";
import { useTheme } from "next-themes";
import { RotatingIcosahedron } from "./scenes/RotatingIcosahedron";

const PRIMARY_LIGHT = "#4338ca";
const PRIMARY_DARK = "#8a93ff";

export default function LoadingSceneInner() {
  const { resolvedTheme } = useTheme();
  const color = resolvedTheme === "dark" ? PRIMARY_DARK : PRIMARY_LIGHT;

  return (
    <Canvas camera={{ position: [0, 0, 4] }}>
      <ambientLight intensity={0.6} />
      <pointLight position={[5, 5, 5]} intensity={0.8} />
      <RotatingIcosahedron color={color} />
    </Canvas>
  );
}
