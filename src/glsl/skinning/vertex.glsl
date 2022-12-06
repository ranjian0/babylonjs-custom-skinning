precision highp float;

// Attributes
attribute vec3 position;
attribute vec3 normal;
attribute vec3 color;

struct BoneFrame {
    mat4 b[3];
};

// Uniforms
uniform float time;
uniform mat4 world;
uniform mat4 worldViewProjection;

const int NUM_BONES = 3;
const int NUM_VERTS = 72;
const int NUM_FRAMES = 100;

uniform vec3 weights[NUM_VERTS];
uniform BoneFrame bones[NUM_FRAMES];

varying vec3 vColor;

void main(void) {
    mat4 boneRes = mat4(0.0);
    int frame = int(mod(time * 0.05, float(NUM_FRAMES)));
    for (int i = 0; i < NUM_BONES; i++) {
        float w = weights[gl_VertexID][i];
        mat4 b = bones[frame].b[i];
        boneRes += b * w;
    }
    vec4 outPosition = worldViewProjection * boneRes * vec4(position, 1.0);
    gl_Position = outPosition;
    vColor = color;
}
    