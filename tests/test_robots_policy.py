"""Most-specific robots rules and bounded wildcard matching; no HTTP calls."""
import pytest

from ayo.robots_policy import RobotsPolicy


AGENT = 'AyoResearch/0.2 (+https://github.com/drippyxx12/Ayo)'


@pytest.mark.parametrize('rules', ['Allow: /\nDisallow: /products/', 'Disallow: /products/\nAllow: /'])
def test_more_specific_denial_wins_regardless_of_file_order(rules):
    policy = RobotsPolicy('User-agent: *\n' + rules)
    assert policy.can_fetch(AGENT, 'https://shop.org/')
    assert not policy.can_fetch(AGENT, 'https://shop.org/products/item')


@pytest.mark.parametrize(('path', 'allowed'), [
    ('/products/private/item', False), ('/products/private/public', True),
    ('/products/private/public/child', False), ('/products/open', True)])
def test_wildcards_and_terminal_anchor_are_respected(path, allowed):
    policy = RobotsPolicy('User-agent: *\nDisallow: /products/private/*\nAllow: /products/private/public$\n')
    assert policy.can_fetch(AGENT, 'https://shop.org' + path) is allowed


def test_specific_agent_groups_merge_and_equal_path_allow_wins():
    policy = RobotsPolicy('''User-agent: *
Disallow: /
User-agent: AyoResearch
Disallow: /catalog
User-agent: AyoResearch
Allow: /catalog
Disallow: /delivery
''')
    assert policy.can_fetch(AGENT, 'https://shop.org/catalog')
    assert policy.can_fetch(AGENT, 'https://shop.org/about')
    assert not policy.can_fetch(AGENT, 'https://shop.org/delivery')
    assert not policy.can_fetch('OtherAgent', 'https://shop.org/about')


def test_encoded_unreserved_path_and_literal_reserved_octets():
    policy = RobotsPolicy('User-agent: *\nDisallow: /%70roducts/\nDisallow: /a%2Fb\n')
    assert not policy.can_fetch(AGENT, 'https://shop.org/products/item')
    assert not policy.can_fetch(AGENT, 'https://shop.org/a%2fb')
    assert policy.can_fetch(AGENT, 'https://shop.org/a/b')


def test_delay_uses_selected_groups_and_conservative_rate_spacing():
    policy = RobotsPolicy('User-agent: *\nCrawl-delay: 50\nUser-agent: AyoResearch\nRequest-rate: 2/10\n')
    assert policy.delay_seconds(AGENT) == 5
    assert policy.delay_seconds('OtherAgent') == 50


def test_many_wildcards_do_not_backtrack_or_accidentally_match_an_absent_suffix():
    policy = RobotsPolicy('User-agent: *\nDisallow: /' + '*a' * 1000 + '*b$\n')
    assert policy.can_fetch(AGENT, 'https://shop.org/' + 'a' * 1500)


def test_empty_rule_allows_and_policy_size_is_bounded():
    assert RobotsPolicy('User-agent: *\nDisallow:\n').can_fetch(AGENT, 'https://shop.org/')
    with pytest.raises(ValueError):
        RobotsPolicy('x' * 200_001)
