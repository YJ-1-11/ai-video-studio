import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame} from 'remotion';

// Author sceneViews in project source. Keys match the timeline's scene IDs.
export function TimelinePicture({timeline, sceneViews, showCaptions = false}) {
  return (
    <AbsoluteFill>
      {timeline.scenes.map(({id, start_frame, end_frame}) => {
        const View = sceneViews[id];
        if (!View) throw new Error('No view for scene ' + id);
        return (
          <Sequence key={id} name={id} from={start_frame} durationInFrames={end_frame - start_frame}>
            <View />
          </Sequence>
        );
      })}
      {showCaptions && <CaptionLayer captions={timeline.captions} />}
    </AbsoluteFill>
  );
}

export function CaptionLayer({captions}) {
  const frame = useCurrentFrame();
  const cue = captions.find((c) => c.start_frame <= frame && frame < c.end_frame);
  if (!cue) return null;
  return (
    <div style={{
      position: 'absolute', bottom: '7%', left: '8%', right: '8%', textAlign: 'center',
      color: '#fff', fontSize: '2.4vw', fontFamily: 'Arial, sans-serif',
      lineHeight: 1.32, whiteSpace: 'pre-line', textShadow: '0 1px 4px #000, 0 2px 10px #000',
    }}>{cue.text}</div>
  );
}
