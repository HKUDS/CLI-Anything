"""Premium harness pack definitions."""

PACKS = {
    "creative-pro": {
        "name": "Creative Pro",
        "price_monthly": 9,
        "description": "Professional creative tools with full CLI harnesses",
        "harnesses": [
            "adobe-photoshop",
            "adobe-illustrator",
            "adobe-after-effects",
            "adobe-premiere",
            "adobe-indesign",
            "adobe-lightroom",
            "adobe-xd",
            "sketch",
            "figma",
            "affinity-photo",
            "affinity-designer",
            "affinity-publisher",
            "capture-one",
            "dxo-photolab",
            "topaz-labs",
            "luminar",
        ],
    },
    "engineering-pro": {
        "name": "Engineering Pro",
        "price_monthly": 9,
        "description": "CAD/CAM/CAE tools for engineering workflows",
        "harnesses": [
            "autocad",
            "solidworks",
            "catia",
            "nx",
            "inventor",
            "fusion360",
            "creo",
            "rhino",
            "grasshopper",
            "ansys",
            "abaqus",
            "comsol",
            "matlab",
            "simulink",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 49,
        "description": "Enterprise software CLIs for business automation",
        "harnesses": [
            "salesforce-cli",
            "sap-cli",
            "oracle-cli",
            "servicenow-cli",
            "jira-cli",
            "confluence-cli",
            "sharepoint-cli",
            "dynamics365-cli",
            "workday-cli",
            "coupa-cli",
            "netsuite-cli",
            "sage-cli",
        ],
    },
    "video-pro": {
        "name": "Video Pro",
        "price_monthly": 9,
        "description": "Professional video editing and production",
        "harnesses": [
            "davinci-resolve",
            "final-cut-pro",
            "adobe-premiere",
            "avid-media-composer",
            "nuke",
            "fusion",
            "after-effects",
            "motion",
            "hitfilm",
            "vegas-pro",
        ],
    },
    "audio-pro": {
        "name": "Audio Pro",
        "price_monthly": 9,
        "description": "Professional audio production and music",
        "harnesses": [
            "pro-tools",
            "ableton-live",
            "logic-pro",
            "cubase",
            "fl-studio",
            "reason",
            "bitwig",
            "reaper",
            "studio-one",
            "nuendo",
        ],
    },
}


def get_pack(name: str) -> dict:
    """Get a pack by name."""
    if name not in PACKS:
        raise ValueError(f"Unknown pack: {name}. Available: {', '.join(PACKS.keys())}")
    return PACKS[name]


def list_packs() -> list:
    """List all available packs."""
    return [
        {
            "name": k,
            "display_name": v["name"],
            "price": f"${v['price_monthly']}/mo",
            "harnesses": len(v["harnesses"]),
            "description": v["description"],
        }
        for k, v in PACKS.items()
    ]
