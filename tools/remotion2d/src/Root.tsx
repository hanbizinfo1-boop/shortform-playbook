import React from "react";
import { Composition } from "remotion";
import { Shorts2D, Plan } from "./Shorts2D";
import { Shots, ShotPlan } from "./Shots";

// 계획(props)은 tools/s7_prep.py 가 만든 public/<작업>/props.json 을 --props 로 넘긴다
export const Root: React.FC = () => (
  <>
  <Composition
    id="Shots"
    component={Shots}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={300}
    defaultProps={{ fps: 30, duration: 10, voice: "", shots: [], captions: [] } as ShotPlan}
    calculateMetadata={({ props }) => ({ fps: props.fps, durationInFrames: Math.max(1, Math.round(props.duration * props.fps)) })}
  />
  <Composition
    id="Shorts2D"
    component={Shorts2D}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={300}
    defaultProps={{ fps: 30, duration: 10, voice: null, scenes: [], captions: [] } as Plan}
    calculateMetadata={({ props }) => ({
      fps: props.fps,
      durationInFrames: Math.max(1, Math.round(props.duration * props.fps)),
    })}
  />
  </>
);
