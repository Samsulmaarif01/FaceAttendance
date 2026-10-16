<!DOCTYPE html>

<html class="dark" lang="en"><head><meta charset="utf-8"/><meta content="width=device-width, initial-scale=1.0" name="viewport"/><meta content="web_dashboard" name="shell-type"/><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=Plus+Jakarta+Sans:wght@600;700&amp;display=swap" rel="stylesheet"/><link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/><style>@layer base{html,body{margin:0;padding:0;}body{overscroll-behavior:none;}main>:first-child{margin-top:0!important;}main>:last-child{margin-bottom:0!important;}}::-webkit-scrollbar{display:none;}</style><script src="https://cdn.tailwindcss.com"></script><script id="tailwind-config">tailwind.config={darkMode:"class",theme:{extend:{"colors":{"primary-container":"#10b981","on-tertiary":"#1000a9","error-container":"#93000a","secondary-fixed":"#89f5e7","secondary-fixed-dim":"#6bd8cb","on-background":"#dae2fd","on-error":"#690005","secondary":"#6bd8cb","on-tertiary-container":"#1d17b2","surface-container-low":"#131b2e","tertiary-fixed":"#e1e0ff","on-error-container":"#ffdad6","outline-variant":"#3c4a42","on-secondary-fixed-variant":"#005049","tertiary-fixed-dim":"#c0c1ff","outline":"#86948a","on-secondary":"#003732","surface-container-high":"#222a3d","surface-container-highest":"#2d3449","on-secondary-container":"#00302b","error":"#ffb4ab","tertiary":"#c0c1ff","on-surface-variant":"#bbcabf","surface-container-lowest":"#060e20","background":"#0b1326","primary":"#4edea3","inverse-primary":"#006c49","on-primary-container":"#00422b","tertiary-container":"#9699ff","surface-bright":"#31394d","surface-tint":"#4edea3","surface-dim":"#0b1326","inverse-on-surface":"#283044","surface":"#0b1326","on-primary-fixed":"#002113","surface-variant":"#2d3449","on-secondary-fixed":"#00201d","on-tertiary-fixed-variant":"#2f2ebe","primary-fixed":"#6ffbbe","secondary-container":"#29a195","on-primary":"#003824","surface-container":"#171f33","primary-fixed-dim":"#4edea3","on-surface":"#dae2fd","on-primary-fixed-variant":"#005236","inverse-surface":"#dae2fd","on-tertiary-fixed":"#07006c"},"borderRadius":{"DEFAULT":"0.25rem","lg":"0.5rem","xl":"0.75rem","full":"9999px"},"spacing":{"space-lg":"1.5rem","margin-kiosk":"3rem","margin":"2rem","gutter":"1.5rem","margin-mobile":"1rem","space-2xl":"3rem","space-sm":"0.5rem","gutter-kiosk":"2rem","space-md":"1rem","space-xs":"0.25rem","space-xl":"2rem"},"fontFamily":{"headline-md":["Plus Jakarta Sans"],"label-lg":["Inter"],"body-md":["Inter"],"body-sm":["Inter"],"title-md":["Inter"],"body-lg":["Inter"],"title-lg":["Plus Jakarta Sans"],"display-kiosk":["Plus Jakarta Sans"],"label-md":["Inter"],"headline-lg":["Plus Jakarta Sans"],"headline-sm":["Plus Jakarta Sans"],"label-sm":["Inter"],"display-kiosk-mobile":["Plus Jakarta Sans"]},"fontSize":{"headline-md":["24px",{"lineHeight":"32px","letterSpacing":"-0.01em","fontWeight":"600"}],"label-lg":["14px",{"lineHeight":"20px","fontWeight":"500"}],"body-md":["14px",{"lineHeight":"20px","fontWeight":"400"}],"body-sm":["12px",{"lineHeight":"16px","fontWeight":"400"}],"title-md":["16px",{"lineHeight":"24px","fontWeight":"600"}],"body-lg":["16px",{"lineHeight":"24px","fontWeight":"400"}],"title-lg":["18px",{"lineHeight":"24px","fontWeight":"600"}],"display-kiosk":["48px",{"lineHeight":"56px","letterSpacing":"-0.02em","fontWeight":"700"}],"label-md":["12px",{"lineHeight":"16px","letterSpacing":"0.02em","fontWeight":"500"}],"headline-lg":["32px",{"lineHeight":"40px","letterSpacing":"-0.01em","fontWeight":"700"}],"headline-sm":["20px",{"lineHeight":"28px","fontWeight":"600"}],"label-sm":["10px",{"lineHeight":"14px","letterSpacing":"0.04em","fontWeight":"600"}],"display-kiosk-mobile":["32px",{"lineHeight":"40px","letterSpacing":"-0.01em","fontWeight":"700"}]}}}}</script></head><body class="bg-surface font-body-md text-body-md text-on-surface antialiased"><header class="fixed top-0 left-0 right-0 h-16 z-50 bg-surface/85 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.25)]"><div class="h-16 w-full px-margin flex items-center justify-between"><div class="flex items-center gap-space-lg"><div class="flex items-center gap-space-sm"><img alt="VeriFace AI Logo" class="h-8 w-auto object-contain" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCJKGSJTFP9bo1Sov2hhZGkw9UQAGJkIpKRdhuVUZkrRPn57F_ajnbV0tEP3kLhhvstmO4Zg5gAkb_FcIv2JuNcyJfWPG1pjUg8BWEZHJBCWPd4bcsKhKdU0dNiAdU6hTvwxqopdbdSbY4EZ04fRJ1hyIjypfwx5LF0LXEIg0AfJfVWCgMZm6nBwVFgBC5TZbBlROwoi2vgG6FgVUU0cjRqQkM_mbdnlF0UdlluJ_OdgEytslyBAJ2CSA"/><span class="font-title-lg text-title-lg text-on-surface tracking-tight">VeriFace AI</span><span class="px-space-xs py-0.5 rounded bg-surface-container-high text-primary font-label-sm text-label-sm uppercase tracking-wider">Enterprise</span></div><nav class="hidden lg:flex items-center gap-space-lg ml-space-md" data-active-classes="text-primary font-title-md"><a class="font-label-lg text-label-lg text-on-surface-variant hover:text-on-surface transition-colors" data-path="kiosk-presensi-live-scan" href="#">Kiosk Presensi (Live Scan)</a><a class="font-label-lg text-label-lg text-on-surface-variant hover:text-on-surface transition-colors" data-path="riwayat-log-kehadiran" href="#">Riwayat &amp; Log Kehadiran</a><a class="font-label-lg text-label-lg text-on-surface-variant hover:text-on-surface transition-colors" data-path="data-karyawan" href="#">Data Karyawan</a><a class="font-label-lg text-label-lg text-on-surface-variant hover:text-on-surface transition-colors" data-path="pengaturan-kamera-sistem" href="#">Pengaturan Kamera/Sistem</a></nav></div><div class="flex items-center gap-space-md"><div class="hidden sm:flex items-center gap-space-xs px-space-sm py-1 rounded bg-surface-container-low"><span class="material-symbols-outlined text-primary text-[18px]">schedule</span><div class="flex items-center gap-1 font-label-md text-label-md text-on-surface"><span class="font-semibold">08:42:15</span><span class="text-on-surface-variant font-label-sm text-label-sm">WIB (GMT+7)</span></div></div><div class="hidden md:flex items-center gap-space-xs px-space-sm py-1 rounded bg-surface-container-low"><span class="w-2 h-2 rounded-full bg-primary animate-pulse"></span><span class="font-label-md text-label-md text-on-surface-variant">Latency:</span><span class="font-label-md text-label-md text-primary font-medium">14ms (Optimal)</span></div><div class="flex items-center gap-space-sm pl-space-sm"><div class="hidden sm:flex flex-col text-right"><span class="font-label-md text-label-md text-on-surface">Budi Santoso</span><span class="font-label-sm text-label-sm text-primary">Lead Operator</span></div><img alt="Profile" class="w-8 h-8 rounded-full object-cover ring-2 ring-primary/20" src="https://lh3.googleusercontent.com/aida-public/AB6AXuAohE_iWmZF_ygtrBuhsVS49uA48xhvssdGsAL7Te7AkuMtRy_jhOYKYtaoxWJYCdqwKoTwuoQ8sYfC7yZQxicBqtQJ7kjXtJnpglqM-dwBHzR4R2vB1BNUSGfA7Rrz9pu6uvLiT_9VgOOIvjTROtkPkHUqs9HWQzpVMbr_ngvy0mvU6FJx71Jx8QxKNJC9xVOySFKI87Qm7f36CNZwTh-JvzLq3h9J_YX2hc_OQwydTUYCDUHRKA7Urg"/></div></div></div></header><aside class="fixed left-0 top-16 bottom-0 w-64 bg-surface-container-lowest shadow-[0_1px_8px_rgba(0,0,0,0.18)] z-40 hidden md:flex flex-col justify-between py-space-md"><div class="px-space-md flex flex-col gap-space-md"><div class="px-space-sm pt-space-xs pb-space-xs font-label-sm text-label-sm text-outline uppercase tracking-wider">Navigasi Kiosk &amp; Sistem</div><nav class="flex flex-col gap-1" data-active-classes="bg-surface-container-high text-primary font-title-md"><a class="flex items-center gap-space-sm px-space-md py-space-sm rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-all font-label-lg text-label-lg" data-path="kiosk-presensi-live-scan" href="#"><span class="material-symbols-outlined text-[20px]">center_focus_strong</span><span>Kiosk Presensi (Live Scan)</span></a><a class="flex items-center gap-space-sm px-space-md py-space-sm rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-all font-label-lg text-label-lg" data-path="riwayat-log-kehadiran" href="#"><span class="material-symbols-outlined text-[20px]">receipt_long</span><span>Riwayat &amp; Log Kehadiran</span></a><a class="flex items-center gap-space-sm px-space-md py-space-sm rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-all font-label-lg text-label-lg" data-path="data-karyawan" href="#"><span class="material-symbols-outlined text-[20px]">badge</span><span>Data Karyawan</span></a><a class="flex items-center gap-space-sm px-space-md py-space-sm rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-all font-label-lg text-label-lg" data-path="pengaturan-kamera-sistem" href="#"><span class="material-symbols-outlined text-[20px]">videocam</span><span>Pengaturan Kamera/Sistem</span></a></nav></div><div class="px-space-md flex flex-col gap-space-sm"><div class="p-space-md rounded-xl bg-surface-container-low flex flex-col gap-space-xs"><div class="flex items-center justify-between"><span class="font-label-sm text-label-sm text-on-surface-variant">AI Inference Node</span><span class="px-1.5 py-0.5 rounded bg-primary-container/20 text-primary font-label-sm text-label-sm">Active</span></div><span class="font-label-md text-label-md text-on-surface">Edge Engine v2.4</span><div class="w-full bg-surface-container h-1.5 rounded-full overflow-hidden mt-1"><div class="bg-primary h-full rounded-full" style="width: 98%"></div></div><div class="flex justify-between items-center text-outline font-label-sm text-label-sm"><span>Confidence Index</span><span class="text-primary">99.4%</span></div></div></div></aside><div class="md:pl-64 flex flex-col min-h-screen bg-surface"><main class="relative w-full pt-16 flex-1 px-margin py-margin"><div class="flex flex-col w-full">
<!-- Top Operational Banner & Mode Selector -->
<div class="w-full flex flex-col lg:flex-row lg:items-center lg:justify-between gap-space-md mb-space-lg">
<div class="flex flex-col">
<div class="flex items-center gap-space-xs mb-1">
<span class="inline-block w-2.5 h-2.5 rounded-full bg-primary animate-pulse"></span>
<span class="font-label-sm text-label-sm uppercase tracking-wider text-primary font-semibold">Terminal Aktif • Kiosk Presensi Mandiri #01</span>
</div>
<h1 class="font-headline-lg text-headline-lg text-on-surface tracking-tight">Presensi Pengenalan Wajah AI</h1>
<p class="font-body-md text-body-md text-on-surface-variant">Sistem verifikasi biometrik nirsentuh berkecepatan tinggi dengan proteksi anti-spoofing cerdas.</p>
</div>
<!-- Quick Mode Toggle (Check-In vs Check-Out) -->
<div class="flex items-center gap-2 p-1.5 bg-surface-container-low rounded-xl shadow-md border-0 self-start lg:self-center">
<button class="flex items-center gap-space-xs px-space-md py-2.5 rounded-lg bg-primary text-on-primary font-title-md text-title-md transition-all shadow-[0_0_16px_rgba(78,222,163,0.35)]" id="btn-mode-in">
<span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">login</span>
<span>Presensi Masuk</span>
<kbd class="ml-1 text-[11px] px-1.5 py-0.5 rounded bg-on-primary/20 font-label-sm text-on-primary">F1</kbd>
</button>
<button class="flex items-center gap-space-xs px-space-md py-2.5 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-all font-title-md text-title-md" id="btn-mode-out">
<span class="material-symbols-outlined text-[20px]">logout</span>
<span>Presensi Pulang</span>
<kbd class="ml-1 text-[11px] px-1.5 py-0.5 rounded bg-surface-container-highest font-label-sm text-outline">F2</kbd>
</button>
</div>
</div>
<!-- Primary Workstation Grid: Left Viewfinder (60%) + Right Instant Match Card (40%) -->
<div class="w-full grid grid-cols-1 lg:grid-cols-12 gap-gutter mb-space-xl">
<!-- LEFT: High-Tech Interactive Viewfinder & Camera Hub (cols 1-7) -->
<div class="lg:col-span-7 flex flex-col gap-space-md">
<div class="relative w-full aspect-[4/3] sm:aspect-[16/10] rounded-2xl overflow-hidden bg-surface-container-lowest shadow-[0_12px_32px_rgba(0,0,0,0.55)] flex items-center justify-center group">
<!-- Live Camera Feed Simulation Background -->
<div class="absolute inset-0 bg-cover bg-center filter brightness-[0.88] contrast-[1.08] transition-transform duration-700 ease-out group-hover:scale-105" data-alt="A POV direct perspective view of a modern glass office entrance corridor. In the center, a confident Southeast Asian male software architect in smart casual navy blazer is standing calmly looking into the camera lens with mild ambient illumination. High-tech biometric teal holographic interface subtle reflections, cinematic deep slate atmosphere, ultra sharp, cinematic lighting, photorealistic." style="background-image: url('https://lh3.googleusercontent.com/aida-public/AB6AXuBVBwk93L_0N7Ii3A3AkbZYeIqEWh0trU5AAjZ1Q9zpm0votjDXH_8_LLrn7XFFZlV8H9S_dj06ry7rO7i8-CYKTbIUWkSHQ6ujliB2P-VIVUoxsfYJ2q7UV4j_kiqOkGdG7jWB8tqNU0SmLs53OlUy6qmDwjdNDJLfU1ciazrI5q90J0neQLOZRim-yuJhzvzZflOpGgh7NYf46bpA3j0YRJyfwkiFr6dhqnBsHqZxUOgcmni4z_WMfw')"></div>
<!-- Ambient Depth Scrim Gradients -->
<div class="absolute inset-0 bg-gradient-to-t from-surface-container-lowest/95 via-transparent to-surface-container-lowest/80 pointer-events-none"></div>
<div class="absolute inset-0 bg-gradient-to-r from-surface-container-lowest/40 via-transparent to-surface-container-lowest/40 pointer-events-none"></div>
<!-- Dynamic Laser Scanning Line (Animates Top to Bottom) -->
<div class="absolute inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-primary to-transparent opacity-80 shadow-[0_0_18px_#4edea3] pointer-events-none transition-all duration-300" style="animation: scanSweep 3.2s cubic-bezier(0.4, 0, 0.2, 1) infinite;"></div>
<!-- Top Camera Header Control Overlay -->
<div class="absolute top-4 inset-x-4 flex items-center justify-between z-20 pointer-events-auto">
<!-- Realtime Liveness Indicator -->
<div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-container-highest/80 backdrop-blur-md shadow-sm">
<span class="w-2 h-2 rounded-full bg-primary animate-ping"></span>
<span class="font-label-sm text-label-sm text-primary uppercase font-bold tracking-wider">Liveness AI 3.0</span>
<span class="text-outline-variant font-label-sm">|</span>
<span class="font-label-sm text-label-sm text-on-surface">Anti-Spoofing Valid</span>
</div>
<!-- Quick Action Buttons -->
<div class="flex items-center gap-1.5 bg-surface-container-highest/80 backdrop-blur-md p-1 rounded-xl">
<button class="p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container-high transition-colors" title="Ganti Input Kamera">
<span class="material-symbols-outlined text-[18px]">cameraswitch</span>
</button>
<button class="p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container-high transition-colors" title="Sesuaikan Pencahayaan">
<span class="material-symbols-outlined text-[18px]">light_mode</span>
</button>
<button class="p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container-high transition-colors" title="Layar Penuh">
<span class="material-symbols-outlined text-[18px]">fullscreen</span>
</button>
</div>
</div>
<!-- Central Biometric Face Reticle & Mesh Overlay -->
<div class="relative z-10 w-64 h-64 sm:w-80 sm:h-80 flex items-center justify-center pointer-events-none">
<!-- Outer Corner Reticle Brackets (Glowing Emerald) -->
<div class="absolute inset-0">
<!-- Top-Left -->
<div class="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-primary rounded-tl-xl shadow-[0_0_12px_#4edea3]"></div>
<!-- Top-Right -->
<div class="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-primary rounded-tr-xl shadow-[0_0_12px_#4edea3]"></div>
<!-- Bottom-Left -->
<div class="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-primary rounded-bl-xl shadow-[0_0_12px_#4edea3]"></div>
<!-- Bottom-Right -->
<div class="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-primary rounded-br-xl shadow-[0_0_12px_#4edea3]"></div>
</div>
<!-- Pulsing Focus Oval Ring -->
<div class="w-56 h-72 sm:w-64 sm:h-80 rounded-[48%] border border-primary/40 shadow-[0_0_24px_rgba(78,222,163,0.25)] flex items-center justify-center relative backdrop-blur-[1px]">
<!-- Subtle Landmark Points (Synthetic Mesh) -->
<svg class="absolute inset-0 w-full h-full text-primary/70" fill="none" viewbox="0 0 100 120" xmlns="http://www.w3.org/2000/svg">
<circle class="animate-pulse" cx="36" cy="42" fill="currentColor" r="1.5"></circle>
<circle class="animate-pulse" cx="64" cy="42" fill="currentColor" r="1.5"></circle>
<circle cx="50" cy="55" fill="currentColor" r="1.2"></circle>
<circle cx="42" cy="72" fill="currentColor" r="1.2"></circle>
<circle cx="58" cy="72" fill="currentColor" r="1.2"></circle>
<circle cx="50" cy="85" fill="currentColor" r="1.8"></circle>
<!-- Connecting Vector Triangulation Lines -->
<path d="M36 42 L50 55 L64 42 M36 42 L50 85 L64 42 M50 55 L42 72 L50 85 L58 72 Z" opacity="0.65" stroke="currentColor" stroke-dasharray="1 1" stroke-width="0.35"></path>
</svg>
<!-- Face Match Verified Lock Icon -->
<div class="w-12 h-12 rounded-full bg-primary/20 backdrop-blur-md flex items-center justify-center text-primary shadow-[0_0_20px_#4edea3]">
<span class="material-symbols-outlined text-[28px]" style="font-variation-settings: 'FILL' 1;">face</span>
</div>
</div>
</div>
<!-- Bottom Guidance / Range Assistant Floating Pill -->
<div class="absolute bottom-4 inset-x-4 flex flex-col sm:flex-row items-center justify-between gap-2 z-20 pointer-events-auto">
<div class="flex items-center gap-2.5 px-4 py-2 rounded-xl bg-surface-container-highest/90 backdrop-blur-lg shadow-lg">
<span class="material-symbols-outlined text-primary text-[20px]" style="font-variation-settings: 'FILL' 1;">check_circle</span>
<div class="flex flex-col">
<span class="font-label-md text-label-md text-on-surface font-semibold">Posisikan Wajah di Tengah Bingkai</span>
<span class="font-body-sm text-body-sm text-primary">Jarak Ideal: 55 cm (Optimal • 99.8% Siap Rekam)</span>
</div>
</div>
<!-- Camera Stream Specs -->
<div class="hidden sm:flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-container-highest/80 backdrop-blur-md">
<span class="font-label-sm text-label-sm text-on-surface-variant font-mono">1080p @ 60 FPS</span>
<span class="w-1.5 h-1.5 rounded-full bg-primary"></span>
<span class="font-label-sm text-label-sm text-primary font-mono">AI 12ms</span>
</div>
</div>
</div>
<!-- Quick Tips & Manual Fallback Bar -->
<div class="w-full flex items-center justify-between p-space-md rounded-xl bg-surface-container-low shadow-sm">
<div class="flex items-center gap-3">
<div class="p-2 rounded-lg bg-surface-container-high text-primary">
<span class="material-symbols-outlined text-[22px]">tips_and_updates</span>
</div>
<div>
<p class="font-title-md text-title-md text-on-surface">Lepaskan Kacamata Hitam atau Topi</p>
<p class="font-body-sm text-body-sm text-on-surface-variant">Pastikan pencahayaan merata untuk mempercepat durasi pengenalan biometrik.</p>
</div>
</div>
<button class="hidden md:flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface font-label-md text-label-md transition-colors">
<span class="material-symbols-outlined text-[18px]">dialpad</span>
<span>Presensi Manual PIN</span>
</button>
</div>
</div>
<!-- RIGHT: Instant Real-Time Verification Card (cols 8-12) -->
<div class="lg:col-span-5 flex flex-col">
<div class="w-full h-full rounded-2xl bg-surface-container p-space-lg flex flex-col justify-between shadow-[0_16px_36px_rgba(0,0,0,0.45)] relative overflow-hidden">
<!-- Glow Highlight Arc in Background -->
<div class="absolute -right-16 -top-16 w-56 h-56 rounded-full bg-primary/10 blur-3xl pointer-events-none"></div>
<div>
<!-- Card Header & Match Confidence Tag -->
<div class="flex items-center justify-between pb-space-md">
<div class="flex items-center gap-2">
<span class="px-2.5 py-1 rounded-full bg-primary-container/20 text-primary font-label-sm text-label-sm uppercase font-semibold flex items-center gap-1">
<span class="w-1.5 h-1.5 rounded-full bg-primary animate-ping"></span>
                Presensi Berhasil
              </span>
<span class="font-label-sm text-label-sm text-on-surface-variant">Baru Saja</span>
</div>
<div class="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-container-highest text-primary font-label-sm text-label-sm font-semibold">
<span class="material-symbols-outlined text-[16px]">verified_user</span>
<span>99.8% Cocok</span>
</div>
</div>
<!-- Employee Portrait & Profile Brief -->
<div class="flex flex-col sm:flex-row items-center sm:items-start gap-space-md pt-2 pb-space-lg">
<div class="relative">
<img class="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl object-cover shadow-lg" data-alt="Portrait photo of Aditya Pratama, a sharp and professional Southeast Asian male in his early 30s with clean hair, wearing a sleek modern navy blue blazer and white crew neck, smiling pleasantly with confidence against a subtle tech gradient background, sharp focus, studio lighting." src="https://lh3.googleusercontent.com/aida-public/AB6AXuB4Sk3zHxa4Qmv8rx7kmXCuI_fReLdWfZbx9DPRHzYTmpKL6uWF2ntG00Z1fkPO_Qz3DiVzuWe-jFK4yjgWVMQlN6ggmtVkkVoIRcSaoJk2LxHVHsxjQ5p5ltuS2FFtdoIkpvtpr0mMgwwvFHXT87aI8SmNnGVgc2-5LgnWm9_ooy56xEqDBaNFyTyh1wR21Xu-8Ga7B4IoReh_xuML_kH5ymetIacOSMPJ6tO34gio0q7sHl1rdOxQdg"/>
<div class="absolute -bottom-2 -right-2 w-7 h-7 rounded-full bg-primary flex items-center justify-center text-on-primary shadow-[0_0_12px_#4edea3]">
<span class="material-symbols-outlined text-[18px]" style="font-variation-settings: 'FILL' 1;">check</span>
</div>
</div>
<div class="flex flex-col text-center sm:text-left">
<h2 class="font-headline-sm text-headline-sm text-on-surface tracking-tight">Aditya Pratama, S.Kom</h2>
<span class="font-body-md text-body-md text-primary font-medium">Senior UX &amp; Interaction Designer</span>
<div class="flex flex-wrap items-center justify-center sm:justify-start gap-2 mt-2">
<span class="px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm font-mono">NIK: EMP-2024089</span>
<span class="px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm">Product &amp; Tech</span>
</div>
</div>
</div>
<!-- Warm Humanized Greeting Pill -->
<div class="p-space-md rounded-xl bg-gradient-to-r from-surface-container-high to-surface-container-low mb-space-md">
<div class="flex items-center gap-2 mb-1">
<span class="material-symbols-outlined text-secondary text-[20px]">waving_hand</span>
<span class="font-title-md text-title-md text-on-surface">Selamat Pagi, Aditya!</span>
</div>
<p class="font-body-sm text-body-sm text-on-surface-variant leading-relaxed">Presensi masuk kamu telah berhasil terdata dalam sistem cloud. Have a wonderful and productive day!</p>
</div>
<!-- Attendance Timestamp & Key Parameters Grid -->
<div class="grid grid-cols-2 gap-space-sm mb-space-md">
<div class="p-space-sm rounded-xl bg-surface-container-low flex flex-col">
<span class="font-label-sm text-label-sm text-on-surface-variant flex items-center gap-1">
<span class="material-symbols-outlined text-[14px]">alarm</span>
                Waktu Presensi
              </span>
<span class="font-headline-sm text-headline-sm text-on-surface font-mono font-semibold mt-0.5">08:14:22 <span class="font-label-sm text-label-sm text-outline">WIB</span></span>
<span class="font-label-sm text-label-sm text-primary font-medium mt-0.5">Tepat Waktu (On-Time)</span>
</div>
<div class="p-space-sm rounded-xl bg-surface-container-low flex flex-col">
<span class="font-label-sm text-label-sm text-on-surface-variant flex items-center gap-1">
<span class="material-symbols-outlined text-[14px]">device_thermostat</span>
                Suhu Tubuh
              </span>
<span class="font-headline-sm text-headline-sm text-on-surface font-mono font-semibold mt-0.5">36.4°C</span>
<span class="font-label-sm text-label-sm text-primary font-medium mt-0.5">Normal (Sehat)</span>
</div>
<div class="p-space-sm rounded-xl bg-surface-container-low flex flex-col">
<span class="font-label-sm text-label-sm text-on-surface-variant flex items-center gap-1">
<span class="material-symbols-outlined text-[14px]">apartment</span>
                Titik Terminal
              </span>
<span class="font-title-md text-title-md text-on-surface font-medium mt-1 truncate">Lobi Utama - Tower A</span>
<span class="font-label-sm text-label-sm text-outline">Lantai 1 • Gate In-04</span>
</div>
<div class="p-space-sm rounded-xl bg-surface-container-low flex flex-col">
<span class="font-label-sm text-label-sm text-on-surface-variant flex items-center gap-1">
<span class="material-symbols-outlined text-[14px]">sync</span>
                Sinkronisasi ERP
              </span>
<span class="font-title-md text-title-md text-primary font-medium mt-1 flex items-center gap-1">
<span class="w-1.5 h-1.5 rounded-full bg-primary"></span>
                Tersinkron
              </span>
<span class="font-label-sm text-label-sm text-outline">ID: TRX-884920</span>
</div>
</div>
</div>
<!-- Confirmation Action Button Bar -->
<div class="pt-space-sm flex items-center gap-space-sm">
<button class="flex-1 py-3 px-space-md rounded-xl bg-primary hover:bg-primary-container text-on-primary font-title-md text-title-md transition-all shadow-[0_4px_16px_rgba(78,222,163,0.3)] flex items-center justify-center gap-2">
<span class="material-symbols-outlined text-[20px]">thumb_up</span>
<span>Konfirmasi &amp; Lanjutkan</span>
</button>
<button class="p-3 rounded-xl bg-surface-container-highest hover:bg-surface-container-high text-on-surface transition-colors flex items-center justify-center" title="Cetak Kartu Akses Tamu / Tiket Presensi">
<span class="material-symbols-outlined text-[20px]">print</span>
</button>
</div>
</div>
</div>
</div>
<!-- BOTTOM SECTION: Real-Time Stats Bar + Live Attendance Event Stream -->
<div class="w-full flex flex-col gap-space-lg">
<!-- 4 Key Executive Performance Counters -->
<div class="grid grid-cols-2 md:grid-cols-4 gap-gutter">
<!-- Counter 1: Total Present -->
<div class="p-space-md rounded-xl bg-surface-container-low flex flex-col justify-between shadow-sm relative overflow-hidden">
<div class="flex items-center justify-between mb-2">
<span class="font-label-md text-label-md text-on-surface-variant">Total Masuk Hari Ini</span>
<div class="w-8 h-8 rounded-lg bg-surface-container-high flex items-center justify-center text-primary">
<span class="material-symbols-outlined text-[18px]">group</span>
</div>
</div>
<div class="flex items-baseline gap-2">
<span class="font-display-kiosk-mobile text-display-kiosk-mobile text-on-surface font-bold">342</span>
<span class="font-title-md text-title-md text-outline">/ 380 Karyawan</span>
</div>
<!-- Mini Progress Bar -->
<div class="w-full bg-surface-container-highest h-1.5 rounded-full mt-3 overflow-hidden">
<div class="bg-primary h-full rounded-full transition-all duration-500" style="width: 90%;"></div>
</div>
<span class="font-label-sm text-label-sm text-primary mt-1.5">90.0% Rasio Kehadiran Fisik</span>
</div>
<!-- Counter 2: On-Time -->
<div class="p-space-md rounded-xl bg-surface-container-low flex flex-col justify-between shadow-sm">
<div class="flex items-center justify-between mb-2">
<span class="font-label-md text-label-md text-on-surface-variant">Tepat Waktu (On-Time)</span>
<div class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
<span class="material-symbols-outlined text-[18px]">schedule</span>
</div>
</div>
<div class="flex items-baseline gap-2">
<span class="font-display-kiosk-mobile text-display-kiosk-mobile text-primary font-bold">328</span>
<span class="font-body-sm text-body-sm text-on-surface-variant">Orang</span>
</div>
<!-- Trend sparkline badge -->
<div class="flex items-center gap-1.5 mt-3 text-primary font-label-sm text-label-sm">
<span class="material-symbols-outlined text-[16px]">trending_up</span>
<span>+3.4% lebih baik dari kemarin</span>
</div>
<span class="font-label-sm text-label-sm text-outline mt-1.5">Batas toleransi: 08:30 WIB</span>
</div>
<!-- Counter 3: Late -->
<div class="p-space-md rounded-xl bg-surface-container-low flex flex-col justify-between shadow-sm">
<div class="flex items-center justify-between mb-2">
<span class="font-label-md text-label-md text-on-surface-variant">Terlambat Datang</span>
<div class="w-8 h-8 rounded-lg bg-error-container/20 flex items-center justify-center text-error">
<span class="material-symbols-outlined text-[18px]">warning</span>
</div>
</div>
<div class="flex items-baseline gap-2">
<span class="font-display-kiosk-mobile text-display-kiosk-mobile text-error font-bold">14</span>
<span class="font-body-sm text-body-sm text-on-surface-variant">Karyawan</span>
</div>
<div class="flex items-center gap-1.5 mt-3 text-error font-label-sm text-label-sm">
<span class="material-symbols-outlined text-[16px]">history_toggle_off</span>
<span>Rata-rata telat 11.2 menit</span>
</div>
<span class="font-label-sm text-label-sm text-outline mt-1.5">Peringatan otomatis terkirim via HR</span>
</div>
<!-- Counter 4: Remote / Permission / Leave -->
<div class="p-space-md rounded-xl bg-surface-container-low flex flex-col justify-between shadow-sm">
<div class="flex items-center justify-between mb-2">
<span class="font-label-md text-label-md text-on-surface-variant">Izin / Cuti / WFH</span>
<div class="w-8 h-8 rounded-lg bg-tertiary-container/20 flex items-center justify-center text-tertiary">
<span class="material-symbols-outlined text-[18px]">home_work</span>
</div>
</div>
<div class="flex items-baseline gap-2">
<span class="font-display-kiosk-mobile text-display-kiosk-mobile text-on-surface font-bold">38</span>
<span class="font-body-sm text-body-sm text-on-surface-variant">Terjadwal</span>
</div>
<div class="flex items-center gap-1.5 mt-3 text-tertiary font-label-sm text-label-sm">
<span class="material-symbols-outlined text-[16px]">check</span>
<span>Disetujui manajer masing-masing</span>
</div>
<span class="font-label-sm text-label-sm text-outline mt-1.5">22 WFH, 11 Cuti, 5 Tugas Luar</span>
</div>
</div>
<!-- Live Event Feed: 4 Recent Scans Log -->
<div class="w-full rounded-2xl bg-surface-container p-space-md sm:p-space-lg shadow-sm">
<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-space-md">
<div class="flex items-center gap-2">
<span class="material-symbols-outlined text-primary text-[22px]">stream</span>
<h3 class="font-title-lg text-title-lg text-on-surface">Log Aktivitas Presensi Langsung (Real-Time Ticker)</h3>
</div>
<div class="flex items-center gap-2">
<span class="w-2 h-2 rounded-full bg-primary animate-ping"></span>
<span class="font-label-sm text-label-sm text-on-surface-variant">Memperbarui otomatis tiap 2 detik</span>
<button class="ml-2 font-label-md text-label-md text-primary hover:underline flex items-center gap-1">
            Lihat Semua
            <span class="material-symbols-outlined text-[16px]">arrow_forward</span>
</button>
</div>
</div>
<!-- Feed Rows -->
<div class="flex flex-col gap-2">
<!-- Feed Row 1 -->
<div class="flex flex-col sm:flex-row sm:items-center justify-between p-space-sm rounded-xl bg-surface-container-low hover:bg-surface-container-high transition-all gap-2">
<div class="flex items-center gap-3">
<img class="w-10 h-10 rounded-full object-cover" data-alt="Close up avatar photo of Jessica Tan, a young Asian female UI designer with glasses and gentle smile, natural daylight, professional corporate headshot." src="https://lh3.googleusercontent.com/aida-public/AB6AXuAasfxmGlMR5ZGeKFnQGlzX8KJLX17ysstDGSbx4TduwyrWDetLuBzJVevoYM8Oqy3wkOPqhtdcnNhQsJAjzH5dOqUxcX33bqxh0_We4mQs-vmmIc857S1hAWTp9pYz5thk-hfL0mSA8NU99qzB9DxHRvhphoGAH4qrKawUlE6WQ0HpFv0E2PhWVqLGBtPTbg7CoIOuwQ2BPFFcKWD-wAkoaGpOWVs77YM0ONkbR6eC4Go6qzIxc3WxjQ"/>
<div class="flex flex-col">
<span class="font-title-md text-title-md text-on-surface">Jessica Tan, B.Des</span>
<span class="font-body-sm text-body-sm text-on-surface-variant">EMP-2023104 • Digital Experience Design</span>
</div>
</div>
<div class="flex items-center justify-between sm:justify-end gap-space-md">
<div class="flex flex-col sm:text-right">
<span class="font-label-md text-label-md text-on-surface font-mono font-medium">08:14:10 WIB</span>
<span class="font-label-sm text-label-sm text-outline">Akurasi 99.4%</span>
</div>
<span class="px-2.5 py-1 rounded-full bg-primary-container/20 text-primary font-label-sm text-label-sm font-semibold flex items-center gap-1">
<span class="w-1.5 h-1.5 rounded-full bg-primary"></span>
              Tepat Waktu
            </span>
</div>
</div>
<!-- Feed Row 2 -->
<div class="flex flex-col sm:flex-row sm:items-center justify-between p-space-sm rounded-xl bg-surface-container-low hover:bg-surface-container-high transition-all gap-2">
<div class="flex items-center gap-3">
<img class="w-10 h-10 rounded-full object-cover" data-alt="Close up avatar photo of Marcus Wijaya, Southeast Asian male DevOps lead in casual black turtleneck, confident friendly look, modern office background." src="https://lh3.googleusercontent.com/aida-public/AB6AXuCCZbFumevTF5hZpTkcaKQvaBCnL241AqgSDebo-3S3LoAR5HJ7HDCUxOm_F-4Pja009RdTQu_Ujv7JMs6ixLf7Lf-xDD5XSVTsTEra09Y4wIP1IFaLwAPWQYj2tKuZ6gJGbd_533NMnlWmi1c9CADgk51JLAcXgtdVf8rFI3b_ryquMX8_a_xclTspMK-brOGWRKm8sMUZR7fMqY6rplejCq_v3VVIu8SzhdnzlGZ4jtl8sC8IRC9zjA"/>
<div class="flex flex-col">
<span class="font-title-md text-title-md text-on-surface">Marcus Wijaya, S.T.</span>
<span class="font-body-sm text-body-sm text-on-surface-variant">EMP-2021045 • DevOps &amp; Cloud Platform</span>
</div>
</div>
<div class="flex items-center justify-between sm:justify-end gap-space-md">
<div class="flex flex-col sm:text-right">
<span class="font-label-md text-label-md text-on-surface font-mono font-medium">08:13:48 WIB</span>
<span class="font-label-sm text-label-sm text-outline">Akurasi 99.9%</span>
</div>
<span class="px-2.5 py-1 rounded-full bg-primary-container/20 text-primary font-label-sm text-label-sm font-semibold flex items-center gap-1">
<span class="w-1.5 h-1.5 rounded-full bg-primary"></span>
              Tepat Waktu
            </span>
</div>
</div>
<!-- Feed Row 3 -->
<div class="flex flex-col sm:flex-row sm:items-center justify-between p-space-sm rounded-xl bg-surface-container-low hover:bg-surface-container-high transition-all gap-2">
<div class="flex items-center gap-3">
<img class="w-10 h-10 rounded-full object-cover" data-alt="Portrait photo of Rian Hidayat, young Indonesian male business analyst wearing grey polo shirt, focused expression, ambient office background." src="https://lh3.googleusercontent.com/aida-public/AB6AXuDfUn902JLkYPN1vXV-u6GgGKIrqKpHCBYP7OFqNCl1GBa2IKWqMZXl5tJrV4re7q_Hjq1B2VxSrcSizFn2cBdRnELQsuZO6l2fL2ZRHZW7xdsg89zwn1rNlSsVQyPAwPZIFLErIWLnhNkGQGFBZbMSS9f-rl7w5cfsfCi6FAOORjgHdn2BWbZjgzD7zFWeXYc0hZP4WnevxcMwnXwn0gvthNhIkpUpM4DgsFDIDWsnyJKLafDxNN04xw"/>
<div class="flex flex-col">
<span class="font-title-md text-title-md text-on-surface">Rian Hidayat</span>
<span class="font-body-sm text-body-sm text-on-surface-variant">EMP-2022177 • Business Analytics</span>
</div>
</div>
<div class="flex items-center justify-between sm:justify-end gap-space-md">
<div class="flex flex-col sm:text-right">
<span class="font-label-md text-label-md text-on-surface font-mono font-medium">08:12:05 WIB</span>
<span class="font-label-sm text-label-sm text-outline">Akurasi 98.6%</span>
</div>
<span class="px-2.5 py-1 rounded-full bg-primary-container/20 text-primary font-label-sm text-label-sm font-semibold flex items-center gap-1">
<span class="w-1.5 h-1.5 rounded-full bg-primary"></span>
              Tepat Waktu
            </span>
</div>
</div>
<!-- Feed Row 4 (Slightly Late Example) -->
<div class="flex flex-col sm:flex-row sm:items-center justify-between p-space-sm rounded-xl bg-surface-container-low hover:bg-surface-container-high transition-all gap-2">
<div class="flex items-center gap-3">
<img class="w-10 h-10 rounded-full object-cover" data-alt="Portrait headshot of Siti Rahmawati, female Indonesian HR specialist with pleasant smile, wearing formal teal blazer, clean lighting." src="https://lh3.googleusercontent.com/aida-public/AB6AXuDKJftqstcaDGrqAScS0tv3tWveUlE6mbyhBIlr8cr8aZQpJBmet32X_uR7wLkgpKT5tsMjBnbenuazgswB4R3DYblCzuQV99rscrSVyIFCtRL1Hbz5lv2xt-qksVkkd8XrUS6YmlGANeqoJvx1qFS-BYPGr8k_e57vdQoAPTpnwB-29N7rH-qEd1uON6eKk9fmMk_8M5Cq6ytFC_qfTVT553WyACIeBLV_YYjv336ylWWghHqhhxr1XQ"/>
<div class="flex flex-col">
<span class="font-title-md text-title-md text-on-surface">Siti Rahmawati, S.Psi</span>
<span class="font-body-sm text-body-sm text-on-surface-variant">EMP-2020012 • People Operations &amp; Talent</span>
</div>
</div>
<div class="flex items-center justify-between sm:justify-end gap-space-md">
<div class="flex flex-col sm:text-right">
<span class="font-label-md text-label-md text-on-surface font-mono font-medium">08:09:15 WIB</span>
<span class="font-label-sm text-label-sm text-outline">Akurasi 99.1%</span>
</div>
<span class="px-2.5 py-1 rounded-full bg-primary-container/20 text-primary font-label-sm text-label-sm font-semibold flex items-center gap-1">
<span class="w-1.5 h-1.5 rounded-full bg-primary"></span>
              Tepat Waktu
            </span>
</div>
</div>
</div>
</div>
</div>
</div>
<script>
  (function initFaceAttendanceKiosk() {
    const btnIn = document.getElementById('btn-mode-in');
    const btnOut = document.getElementById('btn-mode-out');

    if (btnIn && btnOut) {
      btnIn.addEventListener('click', () => {
        btnIn.className = "flex items-center gap-space-xs px-space-md py-2.5 rounded-lg bg-primary text-on-primary font-title-md text-title-md transition-all shadow-[0_0_16px_rgba(78,222,163,0.35)]";
        btnOut.className = "flex items-center gap-space-xs px-space-md py-2.5 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-all font-title-md text-title-md";
      });

      btnOut.addEventListener('click', () => {
        btnOut.className = "flex items-center gap-space-xs px-space-md py-2.5 rounded-lg bg-primary text-on-primary font-title-md text-title-md transition-all shadow-[0_0_16px_rgba(78,222,163,0.35)]";
        btnIn.className = "flex items-center gap-space-xs px-space-md py-2.5 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-all font-title-md text-title-md";
      });

      // Keyboard shortcuts for kiosk operators
      window.addEventListener('keydown', (e) => {
        if (e.key === 'F1') {
          e.preventDefault();
          btnIn.click();
        } else if (e.key === 'F2') {
          e.preventDefault();
          btnOut.click();
        }
      });
    }

    // Add inline keyframe animation dynamically for the scanning laser beam
    if (!document.getElementById('kiosk-laser-style')) {
      const style = document.createElement('style');
      style.id = 'kiosk-laser-style';
      style.textContent = `
        @keyframes scanSweep {
          0% { top: 12%; opacity: 0; }
          15% { opacity: 0.9; }
          85% { opacity: 0.9; }
          100% { top: 88%; opacity: 0; }
        }
      `;
      document.head.appendChild(style);
    }
  })();
</script></main></div></body></html>