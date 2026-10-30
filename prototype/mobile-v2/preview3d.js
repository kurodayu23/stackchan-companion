// mobile-v2 3D 预览模块
// 复刻自 17865 控制台的 motionControlView：官方原厂 GLB 模型 + 浅色舞台 + 1:1 姿态驱动。
// 只保留遥控台需要的部分：模型加载、setPose(yaw,pitch) 阻尼驱动、LED 上色。
import * as THREE from "./vendor/three/three.module.js";
import { GLTFLoader } from "./vendor/three/GLTFLoader.js";

const canvas = document.querySelector("#robotPreviewCanvas");
const fallback = document.querySelector("#robotPreviewFallback");
const stage = document.querySelector("#robotStage");

const MODEL_URL = new URLSearchParams(location.search).get("model") || "assets/stack_chan_model.glb";
// 真机头部的机械范围口径与 17865 控制台一致
const YAW_CLAMP = 128;
const PITCH_MIN = 3;
const PITCH_MAX = 87;
const PITCH_NEUTRAL = 6;

function clampNumber(value, lo, hi, fallbackValue) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallbackValue;
  return Math.max(lo, Math.min(hi, n));
}

export function createPreview() {
  if (!canvas) return null;
  const scene = new THREE.Scene();
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.08;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const camera = new THREE.PerspectiveCamera(27, 1, 0.1, 100);
  camera.position.set(0, 1.08, 6.45);
  camera.lookAt(0, 1.02, 0);

  const keyLight = new THREE.DirectionalLight(0xffffff, 2.5);
  keyLight.position.set(3.8, 5.2, 4.6);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  scene.add(keyLight);
  const fillLight = new THREE.DirectionalLight(0xfff2e6, 0.72);
  fillLight.position.set(-3.4, 2.8, 2.4);
  scene.add(fillLight);
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd9e1ea, 1.35));

  // 浅色舞台：与 17865 控制台相同观感（用户喜欢的版本）
  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(2.12, 96),
    new THREE.MeshStandardMaterial({ color: 0xf4f6f9, roughness: 0.86, metalness: 0 })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.1;
  floor.receiveShadow = true;
  scene.add(floor);

  const modelRoot = new THREE.Group();
  scene.add(modelRoot);

  let foundation = null;
  let fixedPitchBracket = null;
  let headPivot = null;
  let yawAxis = null;
  let pitchAxis = null;
  let yawRotationAxis = "y";
  let targetYaw = 0;
  let targetPitch = 0;
  let poseDamping = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 1 : 0.22;
  let ledMaterials = [];
  let previewSource = "loading";

  function makeBox(width, height, depth, material, x, y, z) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  }

  function makeCircle(radius, material, x, y, z) {
    const mesh = new THREE.Mesh(new THREE.CircleGeometry(radius, 48), material);
    mesh.position.set(x, y, z);
    return mesh;
  }

  function createStackChanPreviewModel() {
    const group = new THREE.Group();
    const body = new THREE.Group();
    foundation = body;
    foundation.name = "fallbackFoundation";
    yawAxis = new THREE.Group();
    yawAxis.name = "yawAxis";
    pitchAxis = new THREE.Group();
    pitchAxis.name = "pitchAxis";
    headPivot = pitchAxis;
    headPivot.position.set(0, 0.92, 0);
    const shell = new THREE.MeshStandardMaterial({ color: 0xe1e4e7, roughness: 0.58, metalness: 0.06 });
    const darkShell = new THREE.MeshStandardMaterial({ color: 0x68717a, roughness: 0.66, metalness: 0.06 });
    const screen = new THREE.MeshStandardMaterial({ color: 0x070809, roughness: 0.34, metalness: 0.1 });
    const face = new THREE.MeshBasicMaterial({ color: 0xf1f5f9 });
    const accent = new THREE.MeshStandardMaterial({ color: 0xa8b0b8, roughness: 0.56, metalness: 0.08 });
    const side = new THREE.MeshStandardMaterial({ color: 0xb9bec6, roughness: 0.62, metalness: 0.06 });
    const baseDark = new THREE.MeshStandardMaterial({ color: 0x59616b, roughness: 0.68, metalness: 0.08 });
    const ledBlue = new THREE.MeshBasicMaterial({ color: 0x60a5fa });
    const ledPink = new THREE.MeshBasicMaterial({ color: 0xf472b6 });
    ledMaterials = [ledBlue, ledPink];

    const headShell = makeBox(1.92, 1.54, 0.5, shell, 0, 0.8, 0);
    const leftSide = makeBox(0.16, 1.46, 0.62, side, -1.04, 0.8, -0.02);
    const rightSide = makeBox(0.16, 1.46, 0.62, side, 1.04, 0.8, -0.02);
    const topLip = makeBox(1.9, 0.11, 0.58, side, 0, 1.61, -0.02);
    const bottomLip = makeBox(1.9, 0.11, 0.58, side, 0, -0.01, -0.02);
    const backPanel = makeBox(1.58, 1.26, 0.08, new THREE.MeshStandardMaterial({ color: 0xcfd4db, roughness: 0.7 }), 0, 0.8, -0.31);
    const topTouch = makeBox(1.18, 0.045, 0.26, new THREE.MeshStandardMaterial({ color: 0xaeb5bf, roughness: 0.62 }), 0, 1.69, -0.02);
    const sideSeamLeft = makeBox(0.025, 1.1, 0.04, darkShell, -0.85, 0.8, 0.3);
    const sideSeamRight = makeBox(0.025, 1.1, 0.04, darkShell, 0.85, 0.8, 0.3);
    const screenPanel = makeBox(1.48, 1.18, 0.065, screen, 0, 0.8, 0.25);
    const leftEye = makeCircle(0.06, face, -0.34, 0.96, 0.292);
    const rightEye = makeCircle(0.06, face, 0.34, 0.96, 0.292);
    const mouth = makeBox(0.3, 0.032, 0.018, face, 0, 0.74, 0.306);
    const powerRing = new THREE.Mesh(
      new THREE.TorusGeometry(0.07, 0.01, 12, 48),
      new THREE.MeshBasicMaterial({ color: 0x8b949e })
    );
    powerRing.position.set(0, 0.39, 0.306);

    const leftLed = new THREE.Mesh(new THREE.SphereGeometry(0.055, 24, 16), ledBlue);
    leftLed.position.set(-0.77, 0.13, 0.29);
    const rightLed = new THREE.Mesh(new THREE.SphereGeometry(0.055, 24, 16), ledPink);
    rightLed.position.set(0.77, 0.13, 0.29);

    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.31, 0.22, 48), accent);
    neck.position.set(0, 0.88, 0);
    neck.castShadow = true;
    neck.receiveShadow = true;

    const neckPlate = makeBox(0.82, 0.12, 0.58, side, 0, 0.76, 0);
    const baseTop = makeBox(1.22, 0.28, 0.9, shell, 0, 0.58, 0);
    const baseMiddle = makeBox(1.36, 0.2, 0.94, baseDark, 0, 0.35, 0);
    const baseBottom = makeBox(1.18, 0.18, 0.86, darkShell, 0, 0.18, 0);
    const leftFoot = makeBox(0.55, 0.13, 0.88, baseDark, -0.34, 0.03, 0);
    const rightFoot = makeBox(0.55, 0.13, 0.88, baseDark, 0.34, 0.03, 0);
    const leftScrew = makeCircle(0.045, new THREE.MeshBasicMaterial({ color: 0x3f4348 }), -0.52, 0.48, 0.48);
    const rightScrew = makeCircle(0.045, new THREE.MeshBasicMaterial({ color: 0x3f4348 }), 0.52, 0.48, 0.48);
    const rearScrewLeft = makeCircle(0.04, new THREE.MeshBasicMaterial({ color: 0x3f4348 }), -0.48, 0.48, -0.48);
    const rearScrewRight = makeCircle(0.04, new THREE.MeshBasicMaterial({ color: 0x3f4348 }), 0.48, 0.48, -0.48);
    leftScrew.rotation.x = -Math.PI / 2;
    rightScrew.rotation.x = -Math.PI / 2;
    rearScrewLeft.rotation.x = Math.PI / 2;
    rearScrewRight.rotation.x = Math.PI / 2;

    headPivot.add(
      headShell, leftSide, rightSide, topLip, bottomLip, backPanel, topTouch,
      sideSeamLeft, sideSeamRight, screenPanel, leftEye, rightEye, mouth,
      powerRing, leftLed, rightLed
    );
    const fallbackPitchAxle = new THREE.Object3D();
    fallbackPitchAxle.name = "fixedPitchAxle";
    fallbackPitchAxle.position.copy(pitchAxis.position);
    fixedPitchBracket = fallbackPitchAxle;
    yawAxis.add(neck, neckPlate, fallbackPitchAxle, pitchAxis);
    body.add(
      baseTop, baseMiddle, baseBottom, leftFoot, rightFoot,
      leftScrew, rightScrew, rearScrewLeft, rearScrewRight
    );
    group.add(body, yawAxis);
    group.scale.setScalar(0.78);
    group.position.y = 0.02;
    yawRotationAxis = "y";
    previewSource = "fallback";
    return group;
  }

  function setLocalTransformFromWorld(object, parent, worldMatrix) {
    parent.updateWorldMatrix(true, false);
    const localMatrix = parent.matrixWorld.clone().invert().multiply(worldMatrix);
    localMatrix.decompose(object.position, object.quaternion, object.scale);
    object.updateMatrixWorld(true);
  }

  function addOfficialExpressionPlane(head) {
    const faceCanvas = document.createElement("canvas");
    faceCanvas.width = 420;
    faceCanvas.height = 320;
    const context = faceCanvas.getContext("2d");
    context.fillStyle = "#08090a";
    context.fillRect(0, 0, faceCanvas.width, faceCanvas.height);
    context.fillStyle = "#f1f5f9";
    context.beginPath();
    context.arc(126, 126, 19, 0, Math.PI * 2);
    context.arc(294, 126, 19, 0, Math.PI * 2);
    context.fill();
    context.fillRect(164, 210, 92, 9);

    const texture = new THREE.CanvasTexture(faceCanvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.flipY = false;
    const material = new THREE.MeshBasicMaterial({ map: texture, side: THREE.DoubleSide });
    const expressionPlane = new THREE.Mesh(new THREE.PlaneGeometry(42, 32), material);
    expressionPlane.name = "expressionPlane";
    expressionPlane.position.set(0, 15.8, 0);
    expressionPlane.rotation.x = -Math.PI / 2;
    expressionPlane.rotation.z = Math.PI;
    head.add(expressionPlane);
  }

  function setupOfficialModel(officialModel) {
    foundation = officialModel.getObjectByName("_00_stackchan450_3");
    const centralComponent = officialModel.getObjectByName("_00_stackchan450_2");
    const head = officialModel.getObjectByName("_00_stackchan450_1");
    const headAssembly = officialModel.getObjectByName("_00_stackchan450_1.001") || head;
    if (!foundation || !centralComponent || !head || !headAssembly) return false;

    officialModel.traverse((node) => {
      if (node.name === "plane" || node.isCamera || node.isLight) node.visible = false;
      if (!node.isMesh) return;
      node.castShadow = true;
      node.receiveShadow = true;
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      materials.filter(Boolean).forEach((material) => {
        if (material.name === "MTL12" || material.name === "MTL12_001") ledMaterials.push(material);
      });
    });

    officialModel.rotation.x = -Math.PI / 2;
    officialModel.updateMatrixWorld(true);
    const initialBounds = new THREE.Box3().setFromObject(officialModel);
    const initialSize = initialBounds.getSize(new THREE.Vector3());
    const largestDimension = Math.max(initialSize.x, initialSize.y, initialSize.z, 1);
    officialModel.scale.setScalar(2.18 / largestDimension);
    officialModel.updateMatrixWorld(true);
    const fittedBounds = new THREE.Box3().setFromObject(officialModel);
    const fittedCenter = fittedBounds.getCenter(new THREE.Vector3());
    officialModel.position.x -= fittedCenter.x;
    officialModel.position.y += 0.02 - fittedBounds.min.y;
    officialModel.position.z -= fittedCenter.z;
    officialModel.updateMatrixWorld(true);

    const centralWorldMatrix = centralComponent.matrixWorld.clone();
    const headWorldMatrix = headAssembly.matrixWorld.clone();
    const foundationBounds = new THREE.Box3().setFromObject(foundation);
    const centralBoundsCenter = new THREE.Box3().setFromObject(centralComponent).getCenter(new THREE.Vector3());
    const pitchPivotWorld = centralComponent.getWorldPosition(new THREE.Vector3());
    pitchPivotWorld.z = centralBoundsCenter.z;
    const yawPivotWorld = new THREE.Vector3(
      pitchPivotWorld.x,
      foundationBounds.max.y,
      pitchPivotWorld.z
    );

    yawAxis = new THREE.Group();
    yawAxis.name = "yawAxis";
    modelRoot.add(yawAxis);
    yawAxis.position.copy(modelRoot.worldToLocal(yawPivotWorld.clone()));
    yawAxis.add(centralComponent);
    setLocalTransformFromWorld(centralComponent, yawAxis, centralWorldMatrix);

    const fixedPitchAxle = new THREE.Object3D();
    fixedPitchAxle.name = "fixedPitchAxle";
    fixedPitchAxle.position.copy(yawAxis.worldToLocal(pitchPivotWorld.clone()));
    yawAxis.add(fixedPitchAxle);
    fixedPitchBracket = fixedPitchAxle;

    pitchAxis = new THREE.Group();
    pitchAxis.name = "pitchAxis";
    yawAxis.add(pitchAxis);
    pitchAxis.position.copy(yawAxis.worldToLocal(pitchPivotWorld.clone()));
    pitchAxis.add(headAssembly);
    setLocalTransformFromWorld(headAssembly, pitchAxis, headWorldMatrix);
    headPivot = head;
    addOfficialExpressionPlane(head);

    yawRotationAxis = "y";
    previewSource = "official-glb";
    return true;
  }

  function setLedColor(red, green, blue) {
    const color = new THREE.Color(red / 255, green / 255, blue / 255);
    ledMaterials.forEach((material) => {
      if (material.color) material.color.copy(color);
      if (material.emissive) material.emissive.copy(color);
      material.needsUpdate = true;
    });
  }

  function setPose(yaw, pitch) {
    targetYaw = THREE.MathUtils.degToRad(THREE.MathUtils.clamp(Number(yaw) || 0, -YAW_CLAMP, YAW_CLAMP));
    const physicalPitch = THREE.MathUtils.clamp(Number(pitch) || 0, PITCH_MIN, PITCH_MAX);
    targetPitch = THREE.MathUtils.degToRad(-(physicalPitch - PITCH_NEUTRAL));
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.floor(rect.width));
    const height = Math.max(1, Math.floor(rect.height));
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  function frame() {
    resize();
    if (yawAxis) {
      const current = yawAxis.rotation[yawRotationAxis];
      yawAxis.rotation[yawRotationAxis] += (targetYaw - current) * poseDamping;
    }
    if (pitchAxis) pitchAxis.rotation.x += (targetPitch - pitchAxis.rotation.x) * poseDamping;
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }

  function useFallbackModel() {
    modelRoot.add(createStackChanPreviewModel());
    setLedColor(60, 120, 168);
    if (fallback) fallback.textContent = "原厂模型暂未加载，已切换到简洁预览";
    stage?.classList.add("has-model");
  }

  if (fallback) fallback.textContent = "正在加载小栈原厂 3D 模型…";
  const loader = new GLTFLoader();
  loader.load(MODEL_URL, (gltf) => {
    modelRoot.add(gltf.scene);
    if (!setupOfficialModel(gltf.scene)) {
      modelRoot.remove(gltf.scene);
      useFallbackModel();
      return;
    }
    setPose(canvas.dataset.yaw || 0, canvas.dataset.pitch || 0);
    setLedColor(60, 120, 168);
    stage?.classList.add("has-model");
    if (fallback) {
      fallback.textContent = "原厂模型已加载：模型与实体 1:1 同步";
      setTimeout(() => { fallback.style.opacity = "0"; }, 1600);
    }
  }, undefined, () => {
    // 加载失败：GLB 缺失 / 离线环境
    useFallbackModel();
  });

  new ResizeObserver(resize).observe(canvas);
  setPose(canvas.dataset.yaw || 0, canvas.dataset.pitch || 0);
  frame();

  return {
    setPose,
    setLedColor,
    getSource: () => previewSource,
  };
}