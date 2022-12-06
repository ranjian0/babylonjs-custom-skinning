import { Engine } from "@babylonjs/core/Engines/engine";
import { WebGPUEngine } from "@babylonjs/core/Engines/webgpuEngine";
import { AbstractMesh, Scene } from "@babylonjs/core";
import "@babylonjs/core/Engines/WebGPU/Extensions/engine.uniformBuffer";
import { ArcRotateCamera } from "@babylonjs/core/Cameras";
import { Vector3 } from "@babylonjs/core/Maths";
import { SceneLoader } from "@babylonjs/core/Loading";
import { HemisphericLight } from "@babylonjs/core/Lights";
import { Effect } from "@babylonjs/core/Materials";
import { ShaderMaterial } from "@babylonjs/core/Materials";
import { CreateGround } from "@babylonjs/core/Meshes/Builders/groundBuilder";
import { StandardMaterial } from "@babylonjs/core/Materials/standardMaterial";
import { Matrix } from "@babylonjs/core/Maths/math.vector";
import { DirectionalLight } from "@babylonjs/core/Lights/directionalLight";
import { ShadowGenerator } from "@babylonjs/core/Lights/Shadows/shadowGenerator";
import "@babylonjs/core/Loading/loadingScreen";
import "@babylonjs/loaders/glTF";
import "@babylonjs/core/Materials/standardMaterial";
import "@babylonjs/core/Materials/Textures/Loaders/envTextureLoader";


import rigMesh from "../assets/glb/rig.glb";
import skinningVertexShader from "./glsl/skinning/vertex.glsl";
import skinningFragmentShader from "./glsl/skinning/fragment.glsl";
import { GLTFFileLoader } from "@babylonjs/loaders/glTF";

type GLTFJsonNode = {
    name: string;
    index: number;
    mesh: number;
    extras: any;
}

type GLTFJson = {
    nodes: Array<GLTFJsonNode>;
}

export const babylonInit = async (): Promise<void> => {
    const canvas = document.getElementById("renderCanvas") as HTMLCanvasElement;
    let engine: Engine;
    const engineType =
        location.search.split("engine=")[1]?.split("&")[0] || "webgl";
    if (engineType === "webgpu") {
        const webGPUSupported = await WebGPUEngine.IsSupportedAsync;
        if (webGPUSupported) {
            const webgpu = engine = new WebGPUEngine(canvas, {
                adaptToDeviceRatio: true,
                antialiasing: true,
            });
            await webgpu.initAsync();
            engine = webgpu;
        } else {
            engine = new Engine(canvas, true);
        }
    } else {
        engine = new Engine(canvas, true);
    }

    const scene = new Scene(engine);
    void Promise.all([
        import("@babylonjs/core/Debug/debugLayer"),
        import("@babylonjs/inspector"),
    ]).then(() => {
        scene.debugLayer.show({
            handleResize: true,
            overlay: true,
            globalRoot: document.getElementById("#root") || undefined,
        });
    });

    const camera = new ArcRotateCamera(
        "cam",
        0,
        Math.PI / 3,
        20,
        new Vector3(0, 0, 0),
        scene
    );
    camera.setTarget(Vector3.Zero());
    camera.attachControl(canvas, true);

    await buildScene(scene);

    engine.runRenderLoop(function () {
        scene.render();
    });
    window.addEventListener("resize", function () {
        engine.resize();
    });
};

async function buildScene(scene: Scene) {
    const ground = CreateGround(
        "ground",
        { width: 20, height: 20 },
        scene
    );

    const groundMaterial = new StandardMaterial("groundmat", scene);
    ground.material = groundMaterial;
    ground.receiveShadows = true;

    const light = new DirectionalLight(
        "light",
        new Vector3(0, -1, 1),
        scene
    );
    light.intensity = 0.7;
    light.position.y = 10;

    const shadowGenerator = new ShadowGenerator(512, light)
    shadowGenerator.useBlurExponentialShadowMap = true;
    shadowGenerator.blurScale = 2;
    shadowGenerator.setDarkness(0.2);

    let shaderTime = 0;
    let boneMats: any = null;
    let boneWeights: any = null;
    const plugin = SceneLoader.Append(
        rigMesh,
        "",
        scene,
        scene => {
            const resulting_mesh = scene.getMeshByName("skinMesh");
            if (resulting_mesh) {
                Effect.ShadersStore["skinningVertexShader"] = skinningVertexShader;
                Effect.ShadersStore["skinningFragmentShader"] = skinningFragmentShader;

                const shaderMaterial = new ShaderMaterial(
                    "skinning",
                    scene,
                    {
                        vertex: "skinning",
                        fragment: "skinning",
                    },
                    {
                        attributes: ["position", "normal", "color", "weights"],
                        defines: [],
                        samplers: [],
                        uniforms: ["cameraPosition", "world", "worldViewProjection", "time"],
                    }
                );

                // time uniform
                scene.registerBeforeRender(() => {
                    // console.log(shaderTime);
                    shaderMaterial.setFloat('time', shaderTime);
                    shaderTime += scene.getEngine().getDeltaTime();
                });

                let counter = 0;
                const shaderWeights = new Float32Array(Object.keys(boneWeights).length * 3);
                for (const vertId in boneWeights) {
                    boneWeights[vertId].forEach((w: number) => {
                        shaderWeights[counter++] = w;
                    });
                }

                // set vertex weights
                for (const vertId in boneWeights) {
                    shaderMaterial.setArray3(
                        `weights[${vertId}]`, 
                        boneWeights[vertId]
                    );
                }

                // set bones matrices
                for (const frameNumber in boneMats) {
                    for (let boneId = 0; boneId < boneMats[frameNumber].length; boneId++ ) {
                        shaderMaterial.setMatrix(
                            `bones[${Number(frameNumber) - 1}].b[${boneId}]`, 
                            Matrix.FromArray(boneMats[frameNumber][boneId])
                        );
                    }
                }

                resulting_mesh.material = shaderMaterial;
                shadowGenerator.getShadowMap()?.renderList?.push(resulting_mesh as AbstractMesh);
            }
        }
    );
    (plugin as GLTFFileLoader).onParsedObservable.add(gltfBabylon => {
        const skinNode = (gltfBabylon.json as GLTFJson).nodes.find(n => n.name === "skinMesh");
        boneMats = skinNode?.extras?.boneMats;
        boneWeights = skinNode?.extras?.boneWeights;
    });
}

babylonInit().then(() => {
    // scene started rendering, everything is initialized
});
