"""Look-dev parameters (one place to tweak the final look). v3: after the art-director review."""
P = dict(
    # exposure / colour (per-shot exposure and bloom are keyed from shots.GRADE)
    exposure=-0.4, look='AgX - Medium High Contrast', gamma=1.0,
    # core: smaller and hotter
    core_power=0.78e5, core_color=(1.0, 0.66, 0.34), core_soft=2.0, core_emit=300.0, core_emit_limb=18.0, core_scale=0.72,
    core_volume=12.0, core_spec=3.0,
    # key moonlight: neutral-cool, hard, raking from camera-left (per-shot direction cheats are keyed from shots.KEY)
    moon_strength=10.0, moon_color=(0.90, 0.94, 1.0), moon_dir=(-0.90, -0.18, 0.40), moon_angle=0.8, moon_spec=0.30,
    # cool back / rim light (shadowless, exterior only)
    rim_strength=2.0, rim_color=(0.50, 0.63, 1.0), rim_dir=(0.75, 0.55, 0.35),
    # world
    world_strength=0.9,
    # fog
    fog_base=0.00012, fog_mist=0.0055, fog_mist_h=20.0, fog_inside=0.00006, fog_halo=0.0016, fog_halo_len=75.0,
    fog_halo_r0=89.0, fog_halo_r1=101.0,
    fog_aniso=0.70, fog_color=(0.80, 0.88, 1.0), fog_noise=0.6, fog_noise_scale=0.012,
    # bloom
    bloom_threshold=2.2, bloom_strength=0.32, bloom_size=0.5, bloom_sat=1.0,
    # rock
    alb_lo=0.18, alb_hi=0.80, det_boost=1.8, fine_strength=0.7, seam_glow=7.0, rim_glow=0.0, seam_far=1.62, cav_dark=0.32,
    rock_dark=(0.052, 0.052, 0.054, 1), rock_light=(0.58, 0.58, 0.585, 1), maria_tint=(0.90, 0.92, 0.96, 1),
    raw_light=(0.10, 0.098, 0.10, 1), seam_color=(1.0, 0.42, 0.10, 1),
    micro_strength=0.55, micro_scale=2.4,
    hull_glow=4.5, hull_seam=0.014,
    # rings
    glyph_glow=1.4, ring_win=4.2, ring_win_tex="ring_windows_v2.png", ring_win_color=(1.0, 0.56, 0.20, 1),
    # environment overrides
    env_rock_mul=(0.42, 0.44, 0.50), env_rock_rough=(0.30, 0.62), env_crest_mul=(0.42, 0.34, 0.46), env_trough_mul=(0.7, 0.7, 0.8),
    env_foam_mul=(0.55, 0.6, 0.68), env_bump_mul=1.0, env_water_rough=(0.10, 0.30),
    remove_islands=True,
    dust_count=800, dust_emit=0.5,
    sea_glint=6.5e5, sea_glint_radius=55.0,
    # stained glass of the rose window
    glass_boost=1.9,
    # probe
    probe=True,
)
