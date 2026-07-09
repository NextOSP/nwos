# Part of NextOSP. See LICENSE file for full copyright and licensing details.

from collections import OrderedDict

from nwos.tools.misc import str2bool


AI_PROVIDER_DEFAULTS = {
    'openrouter': {
        'label': 'OpenRouter',
        'endpoint': 'https://openrouter.ai/api/v1',
        'model': '~openai/gpt-latest',
        'small_model': 'openai/gpt-4o-mini',
        'intelligent_model': '~openai/gpt-latest',
        'email_model': 'openai/gpt-4o-mini',
        'report_model': '~openai/gpt-latest',
    },
    'openai': {
        'label': 'OpenAI',
        'endpoint': 'https://api.openai.com/v1',
        'model': 'gpt-4o-mini',
        'small_model': 'gpt-4o-mini',
        'intelligent_model': 'gpt-4o',
        'email_model': 'gpt-4o-mini',
        'report_model': 'gpt-4o',
    },
    'anthropic': {
        'label': 'Anthropic Claude',
        'endpoint': 'https://api.anthropic.com/v1',
        'model': 'claude-sonnet-4-6',
        'small_model': 'claude-haiku-4-5',
        'intelligent_model': 'claude-sonnet-4-6',
        'email_model': 'claude-haiku-4-5',
        'report_model': 'claude-sonnet-4-6',
    },
    'minimax': {
        'label': 'MiniMax',
        'endpoint': 'https://api.minimaxi.com/v1',
        'model': 'MiniMax-M3',
        'small_model': 'MiniMax-M2.7-highspeed',
        'intelligent_model': 'MiniMax-M3',
        'email_model': 'MiniMax-M2.7-highspeed',
        'report_model': 'MiniMax-M3',
    },
    'kimi': {
        'label': 'Kimi',
        'endpoint': 'https://api.moonshot.ai/v1',
        'model': 'kimi-k2.6',
        'small_model': 'kimi-k2.6',
        'intelligent_model': 'kimi-k2.7-code',
        'email_model': 'kimi-k2.6',
        'report_model': 'kimi-k2.7-code',
    },
    'custom': {
        'label': 'Custom OpenAI-Compatible',
        'endpoint': '',
        'model': '',
        'small_model': '',
        'intelligent_model': '',
        'email_model': '',
        'report_model': '',
    },
}

AI_PROVIDER_SELECTION = [
    (provider, defaults['label'])
    for provider, defaults in AI_PROVIDER_DEFAULTS.items()
]

AI_MODEL_PROFILES = OrderedDict([
    ('default', {
        'label': 'Default / fallback',
        'param': 'base.ai.model',
        'field': 'ai_model',
        'selection_field': 'ai_model_id',
        'default_key': 'model',
        'fallback': None,
    }),
    ('small', {
        'label': 'Fast / small',
        'param': 'base.ai.model.small',
        'field': 'ai_small_model',
        'selection_field': 'ai_small_model_id',
        'default_key': 'small_model',
        'fallback': 'default',
    }),
    ('intelligent', {
        'label': 'Intelligent',
        'param': 'base.ai.model.intelligent',
        'field': 'ai_intelligent_model',
        'selection_field': 'ai_intelligent_model_id',
        'default_key': 'intelligent_model',
        'fallback': 'default',
    }),
    ('email', {
        'label': 'Email',
        'param': 'base.ai.model.email',
        'field': 'ai_email_model',
        'selection_field': 'ai_email_model_id',
        'default_key': 'email_model',
        'fallback': 'intelligent',
    }),
    ('report', {
        'label': 'Report',
        'param': 'base.ai.model.report',
        'field': 'ai_report_model',
        'selection_field': 'ai_report_model_id',
        'default_key': 'report_model',
        'fallback': 'intelligent',
    }),
])

BASE_AI_CONFIG_KEYS = [
    'base.ai.enabled',
    'base.ai.provider',
    'base.ai.endpoint',
    'base.ai.api_key',
    *[meta['param'] for meta in AI_MODEL_PROFILES.values()],
]


def normalize_ai_provider(provider):
    return provider if provider in AI_PROVIDER_DEFAULTS else 'openrouter'


def normalize_ai_profile(profile):
    return profile if profile in AI_MODEL_PROFILES else 'default'


def _clean(value):
    return str(value or '').strip()


def _get_legacy_param(ICP, legacy_prefix, key):
    if not legacy_prefix:
        return None
    return ICP.get_param(f'{legacy_prefix}.{key}', default=None)


def get_ai_profile_model(ICP, provider, profile='default', legacy_prefix=None):
    provider = normalize_ai_provider(provider)
    profile = normalize_ai_profile(profile)
    defaults = AI_PROVIDER_DEFAULTS[provider]
    legacy_model = _get_legacy_param(ICP, legacy_prefix, 'model')
    default_model = _clean(
        ICP.get_param(AI_MODEL_PROFILES['default']['param'], default=None)
        or legacy_model
        or defaults['model']
    )
    if profile == 'default':
        return default_model

    checked_profiles = set()
    current_profile = profile
    while current_profile and current_profile not in checked_profiles:
        checked_profiles.add(current_profile)
        profile_meta = AI_MODEL_PROFILES[current_profile]
        model = _clean(ICP.get_param(profile_meta['param'], default=None))
        if model:
            return model
        current_profile = profile_meta.get('fallback')
        if current_profile == 'default':
            break
    return default_model


def get_ai_settings(env, profile='default', legacy_prefix=None):
    ICP = env['ir.config_parameter'].sudo()
    enabled_value = ICP.get_param('base.ai.enabled', default=None)
    has_base_ai_settings = bool(ICP.search_count([('key', 'in', BASE_AI_CONFIG_KEYS)]))
    if enabled_value is not None:
        enabled = str2bool(enabled_value, False)
    elif has_base_ai_settings:
        enabled = False
    else:
        enabled = str2bool(_get_legacy_param(ICP, legacy_prefix, 'enabled'), False)

    provider = normalize_ai_provider(
        ICP.get_param('base.ai.provider', default=None)
        or _get_legacy_param(ICP, legacy_prefix, 'provider')
        or 'openrouter'
    )
    defaults = AI_PROVIDER_DEFAULTS[provider]
    return {
        'enabled': enabled,
        'provider': provider,
        'provider_label': defaults['label'],
        'endpoint': _clean(
            ICP.get_param('base.ai.endpoint', default=None)
            or _get_legacy_param(ICP, legacy_prefix, 'endpoint')
            or defaults['endpoint']
        ),
        'model': get_ai_profile_model(ICP, provider, profile=profile, legacy_prefix=legacy_prefix),
        'api_key': _clean(
            ICP.get_param('base.ai.api_key', default=None)
            or _get_legacy_param(ICP, legacy_prefix, 'api_key')
            or ''
        ),
        'profile': normalize_ai_profile(profile),
    }
