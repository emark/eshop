#!/usr/bin/perl -w

use strict;
use lib "/home/hosting_locumtest/usr/local/lib/perl5";
use Mojolicious::Lite;
use Mojo::UserAgent;
use DBIx::Custom;
use Validator::Custom;
use utf8;
use v5.10.0;

open (DBCONF,"< app.conf") || die "Error open dbconfig file";
my @appconf=<DBCONF>;
close DBCONF;
chomp @appconf;

my $storename = $appconf[0];
my $secret = ();
@{$secret} = split (',', $appconf[4]);

my $discounts = {split /,/, $appconf[5]};
my $reviewdiscount = $appconf[6];

our $dbi = DBIx::Custom->connect(
			dsn => $appconf[1],
			user => $appconf[2],
			password => $appconf[3],
			option => {mysql_enable_utf8 => 1}
);

$dbi->do('SET NAMES utf8');

our $order = DBIx::Custom::Order->new;

any '/' => sub{
	my $self = shift;
	my $page = {
		url => 'closed'
	};

	$self->stash(
		page => $page,
	);
	$self->render(template => 'closed');
};

any '/*' => sub{
    my $self = shift;
    my $page = {
        url => 'closed'
    };

    $self->stash(
        page => $page,
    );
    $self->render(template => 'closed');
};


app->secrets($secret);
app->hook(before_dispatch => sub {
				my $self = shift;
				$self->req->url->base(Mojo::URL->new(q{http://www.nastartshop.ru/}));
			}
		);
app->start;
