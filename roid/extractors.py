from typing import Union, Any

from roid.interactions import CommandOptionType, Interaction
from roid.objects import Channel, Member, Role


def extract_channel(interaction: Interaction, value: str) -> Channel:
    return interaction.data.resolved.channels[int(value)]


def extract_role(interaction: Interaction, value: str) -> Role:
    return interaction.data.resolved.roles[int(value)]


def extract_user(interaction: Interaction, value: str) -> Member:
    member = interaction.data.resolved.members[int(value)]
    user = interaction.data.resolved.users[int(value)]
    member.user = user

    return member


def extract_mentionable(interaction: Interaction, value: str) -> Union[Role, Member]:
    try:
        return interaction.data.resolved.roles[int(value)]
    except KeyError:
        return extract_user(interaction, value)


def _echo(_: Interaction, v: Any) -> Any:
    return v


OPTION_EXTRACTORS = {
    CommandOptionType.CHANNEL: extract_channel,
    CommandOptionType.ROLE: extract_role,
    CommandOptionType.USER: extract_user,
    CommandOptionType.MENTIONABLE: extract_mentionable,
    CommandOptionType.BOOLEAN: _echo,
    CommandOptionType.STRING: _echo,
    CommandOptionType.NUMBER: _echo,
    CommandOptionType.INTEGER: _echo,
}


def extract_options(interaction: Interaction) -> dict:
    out = {}
    for option in interaction.data.options:
        if option.value is None:
            continue

        out[option.name] = OPTION_EXTRACTORS[option.type](interaction, option.value)
    return out
