#!/usr/bin/perl -w

use strict;
use lib "/home/hosting_locumtest/usr/local/lib/perl5";
use Mojolicious::Lite;
use DBIx::Custom;
use Validator::Custom;
use utf8;
use v5.10.0;

open (DBCONF,"< app.conf") || die "Error open dbconfig file";
my @appconf=<DBCONF>;
close DBCONF;
chomp @appconf;
our $dbi = DBIx::Custom->connect(
			dsn => $appconf[0],
			user => $appconf[1],
			password => $appconf[2],
			option => {mysql_enable_utf8=>1}
);

$dbi->do('SET NAMES utf8');

post '/checkout' => sub {
	my $self = shift;
	my $cartid=$self->session('cartid');
    my $page = {
		'url' => 'checkout',
	};
	$self->stash(
		page => $page,
	);

	my $vc = Validator::Custom->new;
	my $param = $self->req->params->to_hash;
	my $rule = [
		tel => {message => 'error'} => ['not_blank'],
		delivery_type => ['defined'],
		payment_type => ['defined'],
	];
	my $vresult = $vc->validate($param,$rule);
	if($vresult->is_ok){
		$dbi->insert(
			{
				person => $param->{'person'},
				tel => $param->{'tel'},
				email => $param->{'email'},
				address => $param->{'address'},
				delivery => $param->{'delivery_type'},
				payment => $param->{'payment_type'},
				status => 0,
				sysdate => \"NOW()",
				cartid => $cartid,
			},
			table => 'orders',
		);
		my $order_id = $dbi->select(
							column => 'id',
							table => 'orders',
							where => {sign => $sign},
						)->fetch;
		while(my $ref=$result->fetch_hash){
			$dbi->insert(
				{
					productid => $ref->{'id'},
					title => $ref->{'title'},
					price => $ref->{'price'},
					count => $cart->{$ref->{'id'}},
					cartid => $order_id,
				},
				table => 'items',
			);
		};
		return $self->redirect_to('/thankyou');
	}else{
		$self->stash(
        	cart => $cart,
	        products => $result->fetch_hash_all,
	    );
		$self->stash(missing => 1) if $vresult->has_missing;
		$self->stash(messages => $vresult->messages_to_hash) if $vresult->has_invalid;
	}
	$self->render('checkout');
};

app->secret('ReginaSpector');
app->hook(before_dispatch => sub {
				my $self = shift;
				$self->req->url->base(Mojo::URL->new(q{http://ssl.nastartshop.ru/}));
			}
		);
app->start;
