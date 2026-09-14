import { Component, inject, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { NavbarComponent } from '../../../shared/components/navbar/navbar.component';
import { SidebarComponent } from '../../../shared/components/sidebar/sidebar.component';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [RouterOutlet, NavbarComponent, SidebarComponent],
  template: `
    <app-navbar [userName]="userName" (logout)="onLogout()"></app-navbar>
    <div class="layout-body">
      <app-sidebar></app-sidebar>
      <main class="content">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
  styles: [`
    .layout-body { display: flex; }
    .content { flex: 1; padding: 2rem; overflow-y: auto; }
  `]
})
export class MainLayoutComponent implements OnInit {
  private authService = inject(AuthService);
  userName: string = '';

  ngOnInit(): void {
    const account = this.authService.getAccount();
    this.userName = account?.name || 'Usuario';
  }

  onLogout(): void {
    this.authService.logout();
  }
}